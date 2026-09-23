"""수집 소스 — arXiv · Semantic Scholar · RSS · GDELT · Naver (PRD-03 §7)

전부 httpx.AsyncClient 를 쓴다. requests 를 쓰지 않는다 (architecture.md A-5).
"""

import asyncio
import re
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx

from shared.logging import get_logger

from .normalize import clean_html, match_keywords

logger = get_logger("collector.sources")

UA = "secubrief/0.1 (personal news aggregator)"
ARXIV_DELAY = 3.0  # PRD-03 FR-C-3: arXiv 이용약관
_arxiv_lock = asyncio.Lock()

ATOM = "{http://www.w3.org/2005/Atom}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:  # RFC 822 (RSS)
        from email.utils import parsedate_to_datetime

        d = parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


# ────────────────────────────── arXiv ──────────────────────────────


async def fetch_arxiv(client: httpx.AsyncClient, category: str, limit: int) -> list[dict]:
    """cs.CR 은 전량, cs.AI/cs.LG 는 키워드 교차 매칭분만 (FR-35)."""
    async with _arxiv_lock:  # 직렬화 + 3초 간격
        await asyncio.sleep(ARXIV_DELAY)
        r = await client.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"cat:{category}",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": limit,
            },
            timeout=60,
            follow_redirects=True,  # export.arxiv.org 는 https 로 301 한다
        )
    r.raise_for_status()
    root = ET.fromstring(r.text)

    items = []
    for e in root.findall(f"{ATOM}entry"):
        title = " ".join((e.findtext(f"{ATOM}title") or "").split())
        summary = " ".join((e.findtext(f"{ATOM}summary") or "").split())
        abs_url = e.findtext(f"{ATOM}id") or ""
        arxiv_id = abs_url.rstrip("/").split("/")[-1]
        pdf_url = next(
            (l.get("href") for l in e.findall(f"{ATOM}link") if l.get("title") == "pdf"),
            abs_url.replace("/abs/", "/pdf/"),
        )
        kws = match_keywords(f"{title} {summary}")
        # cs.CR 이 아니면 키워드가 걸린 것만 (FR-35)
        if category != "cs.CR" and not kws:
            continue
        items.append({
            "type": "paper",
            "category": "paper",
            "source_url": abs_url,
            "title_original": title,
            "summary_original": summary,
            "authors": [a.findtext(f"{ATOM}name") for a in e.findall(f"{ATOM}author")],
            "published_at": _parse_dt(e.findtext(f"{ATOM}published")),
            "arxiv_id": arxiv_id,
            "doi": e.findtext("{http://arxiv.org/schemas/atom}doi"),
            "pdf_url": pdf_url,
            "venue": None,
            "matched_keywords": kws or ["보안"],
            "_source": f"arxiv:{category}",
        })
    return items


# ──────────────────────── Semantic Scholar ────────────────────────


async def fetch_semantic_scholar(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    try:
        r = await client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "limit": min(limit, 100),
                "fields": "title,abstract,authors,venue,year,externalIds,openAccessPdf,url",
                "fieldsOfStudy": "Computer Science",
            },
            timeout=60,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"Semantic Scholar 실패: {e}")
        return []

    items = []
    for p in r.json().get("data", []):
        title = p.get("title") or ""
        abstract = p.get("abstract") or ""
        ext = p.get("externalIds") or {}
        url = p.get("url")
        if not url or not title:
            continue
        items.append({
            "type": "paper",
            "category": "paper",
            "source_url": url,
            "title_original": title,
            "summary_original": abstract,
            "authors": [a.get("name") for a in (p.get("authors") or [])],
            "published_at": _parse_dt(f"{p['year']}-01-01") if p.get("year") else None,
            "arxiv_id": ext.get("ArXiv"),
            "doi": ext.get("DOI"),
            "pdf_url": (p.get("openAccessPdf") or {}).get("url"),
            "venue": p.get("venue"),
            "matched_keywords": match_keywords(f"{title} {abstract}") or ["보안"],
            "_source": "semantic_scholar",
        })
    return items


# ────────────────────────────── RSS ──────────────────────────────


async def fetch_rss(client: httpx.AsyncClient, name: str, url: str, category: str) -> list[dict]:
    try:
        r = await client.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"RSS 실패 [{name}]: {e}")
        return []

    import feedparser

    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries:
        title = clean_html(getattr(e, "title", ""))
        link = getattr(e, "link", "")
        if not title or not link:
            continue
        summary = clean_html(getattr(e, "summary", "") or getattr(e, "description", ""))
        thumb = None
        for key in ("media_thumbnail", "media_content"):
            v = getattr(e, key, None)
            if v and isinstance(v, list) and v[0].get("url"):
                thumb = v[0]["url"]
                break
        items.append({
            "type": "news",
            "category": category,
            "source_url": link,
            "title_original": title,
            "summary_original": summary or None,  # FR-53
            "published_at": _parse_dt(getattr(e, "published", None)),
            "thumbnail_url": thumb,
            "matched_keywords": match_keywords(f"{title} {summary}"),
            "_source": f"rss:{name}",
        })
    return items


# ────────────────────────────── GDELT ──────────────────────────────


async def fetch_gdelt(client: httpx.AsyncClient, query: str, limit: int) -> list[dict]:
    """무료·키 불필요 (PRD-03 FR-36)."""
    try:
        r = await client.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": f"{query} sourcelang:english",
                "mode": "ArtList",
                "maxrecords": min(limit, 250),
                "format": "json",
                "sort": "datedesc",
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:  # noqa: BLE001  JSON 깨짐도 흔하다
        logger.warning(f"GDELT 실패: {e}")
        return []

    items = []
    for a in data.get("articles", []):
        title, url = a.get("title"), a.get("url")
        if not title or not url:
            continue
        items.append({
            "type": "news",
            "category": "international",
            "source_url": url,
            "title_original": title,
            "summary_original": None,  # GDELT 는 요약을 안 준다 → FR-53
            "published_at": _parse_dt(
                re.sub(r"(\d{8})T(\d{6})Z", r"\1T\2Z", a.get("seendate", ""))
                .replace("T", "T")
            ),
            "thumbnail_url": a.get("socialimage") or None,
            "matched_keywords": match_keywords(title),
            "_source": "gdelt",
        })
    return items


# ────────────────────────────── Naver ──────────────────────────────


async def fetch_naver(
    client: httpx.AsyncClient, query: str, limit: int, client_id: str, client_secret: str
) -> list[dict]:
    if not client_id or not client_secret:
        logger.warning("Naver API 키 없음 — 건너뜀 (FR-25 부분 실패 허용)")
        return []
    try:
        r = await client.get(
            "https://openapi.naver.com/v1/search/news.json",
            params={"query": query, "display": min(limit, 100), "sort": "date"},
            headers={"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret},
            timeout=30,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"Naver 실패: {e}")
        return []

    items = []
    for it in r.json().get("items", []):
        title = clean_html(it.get("title", ""))
        link = it.get("originallink") or it.get("link")
        if not title or not link:
            continue
        desc = clean_html(it.get("description", ""))
        items.append({
            "type": "news",
            "category": "domestic",
            "source_url": link,
            "title_original": title,
            "summary_original": desc or None,
            "published_at": _parse_dt(it.get("pubDate")),
            "matched_keywords": match_keywords(f"{title} {desc}"),
            "_source": "naver",
        })
    return items
