"""secubrief API — architecture.md §9

CORS 를 넣지 않는다. Caddy 가 단일 오리진으로 묶는다 (§7.4).
"""

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.db import get_db
from shared.logging import get_logger

from . import queries
from .routes_auth import router as auth_router
from .schemas import ListOut, MainOut, PaperOut, SectionOut, to_card

logger = get_logger("backend")
app = FastAPI(title="secubrief API", docs_url="/docs")

logger.info("Backend starting", {"config": settings.safe_dump()})

app.include_router(auth_router)

MAIN_NEWS = 9  # PRD-04 §8
MAIN_PAPERS = 6


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as e:  # noqa: BLE001
        logger.error("DB connection failed", {"error": str(e)[:200]})
        return {"status": "ok", "db": "error"}


@app.get("/main", response_model=MainOut)
async def main_bundle(db: AsyncSession = Depends(get_db)):
    """메인 번들 — 1회 왕복으로 뉴스 9 + 논문 6 (PRD-04 FR-14)."""
    sql = text(
        f"SELECT {queries.CARD_COLS} FROM contents WHERE type = :t"
        " ORDER BY collected_at DESC, id DESC LIMIT :n"
    )
    news = (await db.execute(sql, {"t": "news", "n": MAIN_NEWS})).all()
    papers = (await db.execute(sql, {"t": "paper", "n": MAIN_PAPERS})).all()
    return MainOut(news=[to_card(r) for r in news], papers=[to_card(r) for r in papers])


@app.get("/contents", response_model=ListOut)
async def contents(
    q: str | None = None,
    type: str | None = Query(None, pattern="^(news|paper)$"),
    category: str | None = Query(None, pattern="^(international|domestic|paper)$"),
    kw: str | None = None,
    sort: str = Query("recent", pattern="^(recent|relevance)$"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """목록 통합 — 검색·카테고리·필터·정렬·페이지 (architecture.md §9)."""
    if q is not None:
        q = q.strip()
        # 2그램 특성상 1글자 질의는 노이즈가 심하다 (PRD-05 FR-21)
        if len(q) < 2:
            raise HTTPException(400, "검색어는 2글자 이상이어야 합니다")

    kw_list = [k.strip() for k in kw.split(",") if k.strip()] if kw else None
    list_sql, count_sql, params, scope = queries.build(
        q, type, category, kw_list, sort, page, size
    )

    total = (await db.execute(text(count_sql), params)).scalar() or 0
    rows = (await db.execute(text(list_sql), params)).all()

    if q:
        await db.execute(queries.LOG_SEARCH, {"q": q, "n": total})
        await db.commit()

    return ListOut(
        items=[to_card(r) for r in rows],
        total=total, page=page, size=size, appliedScope=scope,
    )


@app.get("/papers/{paper_id}", response_model=PaperOut)
async def paper_detail(paper_id: int, db: AsyncSession = Depends(get_db)):
    """논문 상세 — 3섹션 원문/번역 (PRD-04 §10).

    full_text_original 은 내려주지 않는다 (FR-29).
    """
    r = (await db.execute(text("""
        SELECT id, type, title_original, title_ko, collected_at, published_at,
               source_url, pdf_url, authors, venue, doi, arxiv_id,
               sections, section_extract_status, translation_status, matched_keywords
          FROM contents WHERE id = :i AND type = 'paper'
    """), {"i": paper_id})).first()

    if not r:
        raise HTTPException(404, "논문을 찾을 수 없습니다")

    order = {"Abstract": 0, "Introduction": 1, "Conclusion": 2}
    secs = sorted(r.sections or [], key=lambda s: order.get(s.get("name"), 9))

    return PaperOut(
        id=r.id,
        titleDisplay=r.title_ko or r.title_original,
        titleOriginal=r.title_original,
        collectedAt=r.collected_at,
        publishedAt=r.published_at,
        sourceUrl=r.source_url,
        pdfUrl=r.pdf_url,
        authors=list(r.authors or []),
        venue=r.venue,
        doi=r.doi,
        arxivId=r.arxiv_id,
        sections=[SectionOut(**s) for s in secs],
        sectionExtractStatus=r.section_extract_status,
        translationStatus=r.translation_status,
        matchedKeywords=list(r.matched_keywords or []),
    )
