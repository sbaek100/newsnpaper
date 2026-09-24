"""API 응답 스키마 — architecture.md §9

🔴 서버가 완성된 값을 내려준다. 클라이언트가 조합·분기하지 않는다 (A-9).
- titleDisplay / summaryDisplay 는 서버가 폴백을 적용해 계산 (PRD-03 FR-30~32)
- fullTextOriginal 은 어떤 응답에도 넣지 않는다 (색인 전용, PRD-04 FR-29)
- 논문에는 thumbnailUrl 을 넣지 않는다 (PRD-04 §4.2)
"""

from datetime import datetime

from pydantic import BaseModel


class CardOut(BaseModel):
    id: int
    type: str
    category: str
    titleDisplay: str
    summaryDisplay: str | None = None
    collectedAt: datetime
    publishedAt: datetime | None = None
    sourceUrl: str
    matchedKeywords: list[str] = []
    # 뉴스 전용
    thumbnailUrl: str | None = None
    # 논문 전용
    authors: list[str] | None = None
    venue: str | None = None
    sectionExtractStatus: str | None = None


class ListOut(BaseModel):
    items: list[CardOut]
    total: int
    page: int
    size: int
    appliedScope: str


class MainOut(BaseModel):
    news: list[CardOut]
    papers: list[CardOut]


class SectionOut(BaseModel):
    name: str
    textOriginal: str | None = None
    textKo: str | None = None


class PaperOut(BaseModel):
    id: int
    titleDisplay: str
    titleOriginal: str
    collectedAt: datetime
    publishedAt: datetime | None = None
    sourceUrl: str
    pdfUrl: str | None = None
    authors: list[str] | None = None
    venue: str | None = None
    doi: str | None = None
    arxivId: str | None = None
    sections: list[SectionOut] = []
    sectionExtractStatus: str | None = None
    translationStatus: str
    matchedKeywords: list[str] = []


def to_card(r) -> CardOut:
    """DB 행 → 카드. 폴백을 여기서 한 번만 적용한다."""
    is_paper = r.type == "paper"
    return CardOut(
        id=r.id,
        type=r.type,
        category=r.category,
        titleDisplay=r.title_ko or r.title_original,
        summaryDisplay=r.summary_ko or r.summary_original,
        collectedAt=r.collected_at,
        publishedAt=r.published_at,
        sourceUrl=r.source_url,
        matchedKeywords=list(r.matched_keywords or []),
        thumbnailUrl=None if is_paper else r.thumbnail_url,
        authors=list(r.authors or []) if is_paper else None,
        venue=r.venue if is_paper else None,
        sectionExtractStatus=r.section_extract_status if is_paper else None,
    )
