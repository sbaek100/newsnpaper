"""수집 배치 — dedup → PDF 파싱 → 저장 → 번역 큐 적재

네트워크는 async, PDF 파싱은 ProcessPoolExecutor (architecture.md §4.5.3, A-6).
"""

import asyncio
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import httpx
from sqlalchemy import select, text

from shared.config import settings
from shared.db import AsyncSessionLocal
from shared.logging import get_logger
from shared.models import BatchRun, Content, Source, TranslationJob

from . import sources as S
from .normalize import detect_language, normalize_url
from .pdf import parse_pdf

logger = get_logger("collector.pipeline")

EN_QUERY = "security OR hacking OR cyber OR malware OR vulnerability"
KO_QUERY = "보안"


# ───────────────────────── dedup (PRD-03 §4.2) ─────────────────────────


def dedup(items: list[dict]) -> tuple[list[dict], int]:
    """URL 정규화 + DOI/arXiv ID 기준 병합.

    🔴 제목 유사도로 병합하지 않는다 (FR-64). 확신이 없으면 남긴다 (FR-63).
    """
    by_key: dict[str, dict] = {}
    merged = 0

    def info_score(it: dict) -> int:
        return sum(bool(it.get(k)) for k in
                   ("pdf_url", "summary_original", "authors", "venue", "thumbnail_url"))

    for it in items:
        it["source_url_norm"] = normalize_url(it["source_url"])
        # 논문은 DOI/arXiv ID 우선 (FR-C-16)
        key = None
        if it.get("doi"):
            key = f"doi:{it['doi'].lower()}"
        elif it.get("arxiv_id"):
            key = f"arxiv:{it['arxiv_id'].split('v')[0].lower()}"
        else:
            key = f"url:{it['source_url_norm']}"

        prev = by_key.get(key)
        if prev is None:
            by_key[key] = it
            continue
        merged += 1
        # 정보가 더 많은 쪽을 남긴다 (FR-C-17)
        keep, drop = (it, prev) if info_score(it) > info_score(prev) else (prev, it)
        for k, v in drop.items():
            if v and not keep.get(k):
                keep[k] = v
        by_key[key] = keep
        logger.info("병합", {"key": key, "reason": key.split(":")[0]})  # FR-65

    return list(by_key.values()), merged


# ───────────────────────── 수집 ─────────────────────────


async def gather_all(limit_news: int, limit_papers: int) -> tuple[list[dict], Counter]:
    stats: Counter = Counter()

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Source).where(Source.enabled.is_(True)))).scalars().all()
        srcs = [{"kind": r.kind, "name": r.name, "url": r.url, "category": r.category} for r in rows]

    async with httpx.AsyncClient(headers={"User-Agent": S.UA}) as client:
        tasks, labels = [], []

        for s in srcs:
            if s["kind"] == "rss":
                tasks.append(S.fetch_rss(client, s["name"], s["url"], s["category"]))
            elif s["kind"] == "arxiv":
                cat = s["name"].split()[-1]  # "arXiv cs.CR" → cs.CR
                n = limit_papers if cat == "cs.CR" else max(limit_papers, 50)
                tasks.append(S.fetch_arxiv(client, cat, n))
            elif s["name"] == "GDELT DOC":
                tasks.append(S.fetch_gdelt(client, EN_QUERY, limit_news))
            elif s["name"] == "Naver News":
                tasks.append(S.fetch_naver(client, KO_QUERY, limit_news,
                                           settings.naver_client_id,
                                           settings.naver_client_secret))
            else:
                continue
            labels.append(s["name"])

        tasks.append(S.fetch_semantic_scholar(client, EN_QUERY, limit_papers))
        labels.append("Semantic Scholar")

        # FR-25: 부분 실패 허용
        results = await asyncio.gather(*tasks, return_exceptions=True)

    items: list[dict] = []
    for label, res in zip(labels, results):
        if isinstance(res, Exception):
            logger.warning(f"소스 실패 [{label}]: {res}")
            stats[f"fail:{label}"] += 1
            continue
        stats[f"ok:{label}"] = len(res)
        items.extend(res)
    return items, stats


# ───────────────────────── PDF (CPU 병렬) ─────────────────────────


async def _download(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        r = await client.get(url, timeout=90, follow_redirects=True)
        r.raise_for_status()
        return r.content
    except Exception as e:  # noqa: BLE001
        logger.warning(f"PDF 다운로드 실패 {url}: {e}")
        return None


async def process_pdfs(papers: list[dict]) -> Counter:
    """PDF 를 받아 프로세스 풀에서 파싱한다. PDF 는 메모리에서만 다루고 저장하지 않는다 (FR-51)."""
    stats: Counter = Counter()
    if not papers:
        return stats

    loop = asyncio.get_running_loop()
    sem = asyncio.Semaphore(6)  # 서버 부담 방지

    async with httpx.AsyncClient(headers={"User-Agent": S.UA}) as client:
        async def one(p: dict) -> tuple[dict, bytes | None]:
            if not p.get("pdf_url"):
                return p, None
            async with sem:
                return p, await _download(client, p["pdf_url"])

        downloaded = await asyncio.gather(*[one(p) for p in papers])

    with ProcessPoolExecutor(max_workers=settings.collector_workers) as pool:
        jobs = []
        for p, blob in downloaded:
            if blob is None:
                p["sections"] = ([{"name": "Abstract",
                                   "textOriginal": p.get("summary_original") or "",
                                   "textKo": None}]
                                 if p.get("summary_original") else [])
                p["section_extract_status"] = "abstract_only" if p["sections"] else "failed"
                p["full_text_status"] = "no_pdf"  # FR-29b
                p["full_text_original"] = None
                stats["no_pdf"] += 1
                continue
            jobs.append((p, loop.run_in_executor(
                pool, parse_pdf, blob, p.get("summary_original") or "")))

        for p, fut in jobs:
            res = await fut
            p["sections"] = [
                {"name": n, "textOriginal": t, "textKo": None}
                for n, t in res["sections"].items()
            ]
            p["section_extract_status"] = res["status"]
            p["full_text_original"] = res["full_text"] or None
            p["full_text_status"] = "indexed" if res["full_text"] else "extract_failed"
            stats[f"section:{res['status']}"] += 1

    return stats


# ───────────────────────── 저장 + 번역 큐 ─────────────────────────


async def persist(items: list[dict]) -> Counter:
    stats: Counter = Counter()
    async with AsyncSessionLocal() as db:
        # 이미 있는 것 제외 (FR-C-19)
        urls = [i["source_url"] for i in items]
        existing = set((await db.execute(
            text("SELECT source_url FROM contents WHERE source_url = ANY(:u)"),
            {"u": urls})).scalars().all())

        for it in items:
            if it["source_url"] in existing:
                stats["skip_existing"] += 1
                continue

            blob = f"{it['title_original']} {it.get('summary_original') or ''}"
            lang = detect_language(blob)
            # FR-10: 이미 한국어면 번역 제외
            status = "skipped" if lang == "ko" else "pending"

            # sections 는 JSONB. None 을 명시적으로 넘기면 asyncpg 가
            # "cannot extract elements from a scalar" 로 죽는다. 값이 있을 때만 넣는다.
            optional = {}
            if it.get("sections") is not None:
                optional["sections"] = it["sections"]

            c = Content(
                type=it["type"],
                category=it["category"],
                source_url=it["source_url"],
                language=lang,
                title_original=it["title_original"],
                title_ko=it["title_original"] if lang == "ko" else None,
                translation_status=status,
                matched_keywords=it.get("matched_keywords") or [],
                thumbnail_url=it.get("thumbnail_url"),
                summary_original=it.get("summary_original"),
                summary_ko=it.get("summary_original") if lang == "ko" else None,
                authors=it.get("authors"),
                venue=it.get("venue"),
                published_at=it.get("published_at"),
                doi=it.get("doi"),
                arxiv_id=it.get("arxiv_id"),
                pdf_url=it.get("pdf_url"),
                section_extract_status=it.get("section_extract_status"),
                full_text_original=it.get("full_text_original"),
                full_text_status=it.get("full_text_status"),
                **optional,
            )
            # 건별 격리 — 한 건이 배치 전체를 죽이지 않게
            try:
                async with db.begin_nested():
                    db.add(c)
                    await db.flush()
            except Exception as e:  # noqa: BLE001
                stats["insert_fail"] += 1
                logger.warning("저장 실패", {
                    "url": it["source_url"], "source": it.get("_source"),
                    "error": str(e)[:200],
                })
                continue
            stats[f"saved:{it['type']}"] += 1

            if status == "skipped":
                continue

            # 번역 큐 (FR-30~35). full_text 는 넣지 않는다 (FR-34)
            fields = ["title"]
            if it.get("summary_original"):
                fields.append("summary")
            for sec in it.get("sections") or []:
                if sec.get("textOriginal"):
                    fields.append(f"section:{sec['name']}")
            for f in fields:
                db.add(TranslationJob(content_id=c.id, field=f))
            stats["jobs"] += len(fields)

        await db.commit()
    return stats


# ───────────────────────── 엔트리 ─────────────────────────


async def run_batch() -> dict:
    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        run = BatchRun()
        db.add(run)
        await db.commit()
        run_id = run.id

    stats: Counter = Counter()
    try:
        items, s1 = await gather_all(settings.batch_limit_news, settings.batch_limit_papers)
        stats.update(s1)
        stats["fetched"] = len(items)

        items, merged = dedup(items)
        stats["merged"] = merged

        # 상한 적용 — 최신순으로 자른다 (FR-27, C-12).
        # 🔴 카테고리별 쿼터로 나눈다. 전체를 한 번에 자르면 국내 뉴스가
        #    국제 뉴스에 밀려 0건이 되는 일이 생긴다 (2026-09-23 실측).
        def newest(pool: list[dict], n: int) -> list[dict]:
            return sorted(
                pool,
                key=lambda i: (i.get("published_at") is not None, i.get("published_at")),
                reverse=True,
            )[:n]

        n_intl = settings.batch_limit_news * 6 // 10
        n_dom = settings.batch_limit_news - n_intl
        intl = newest([i for i in items if i["category"] == "international"], n_intl)
        dom = newest([i for i in items if i["category"] == "domestic"], n_dom)
        # 한쪽이 쿼터를 못 채우면 남은 자리를 다른 쪽이 쓴다
        spare = settings.batch_limit_news - len(intl) - len(dom)
        if spare > 0:
            taken = {id(x) for x in intl + dom}
            rest = [i for i in items if i["type"] == "news" and id(i) not in taken]
            intl += newest(rest, spare)
        news = intl + dom
        papers = newest([i for i in items if i["type"] == "paper"], settings.batch_limit_papers)
        stats["after_limit_intl"] = len(intl)
        stats["after_limit_dom"] = len(dom)
        stats["after_limit_news"] = len(news)
        stats["after_limit_papers"] = len(papers)

        stats.update(await process_pdfs(papers))
        stats.update(await persist(news + papers))
        status = "done"
    except Exception as e:  # noqa: BLE001
        logger.error("배치 실패", {"error": str(e)[:500]})
        stats["error"] = str(e)[:500]
        status = "failed"

    stats["elapsed_sec"] = round(time.monotonic() - t0, 1)
    async with AsyncSessionLocal() as db:
        r = await db.get(BatchRun, run_id)
        r.status = status
        r.stats = dict(stats)
        r.finished_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc)
        await db.commit()

    logger.info("배치 완료", {"stats": dict(stats)})
    return dict(stats)
