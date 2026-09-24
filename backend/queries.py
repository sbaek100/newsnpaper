"""목록·검색 질의 — PRD-05, PRD-06

한국어는 pg_bigm, 영어는 tsvector. 기본 정렬은 어디서나 최신순 (2026-09-23 지시).
"""

import re

from sqlalchemy import text

HANGUL = re.compile(r"[가-힯]")

CARD_COLS = """
    id, type, category, title_original, title_ko, summary_original, summary_ko,
    collected_at, published_at, source_url, matched_keywords, thumbnail_url,
    authors, venue, section_extract_status
"""

SCOPE_KO = "제목·요약·논문 초록 (번역문)"
SCOPE_EN = "제목·요약·논문 초록 + 논문 본문 (원문)"
SCOPE_BOTH = "제목·요약·논문 초록 (번역문) + 논문 본문 (원문)"
SCOPE_NONE = "최신순 목록"


def build(
    q: str | None,
    type_: str | None,
    category: str | None,
    kw: list[str] | None,
    sort: str,
    page: int,
    size: int,
) -> tuple[str, str, dict, str]:
    """(목록 SQL, 카운트 SQL, 파라미터, appliedScope) 반환."""
    where: list[str] = []
    params: dict = {}

    if type_:
        where.append("type = :type")
        params["type"] = type_
    if category:
        where.append("category = :category")
        params["category"] = category
    if kw:
        # matched_keywords 다중 선택은 OR, 다른 필터와는 AND (PRD-06 §9.3)
        where.append("matched_keywords && CAST(:kw AS text[])")
        params["kw"] = kw

    scope = SCOPE_NONE
    if q:
        has_ko = bool(HANGUL.search(q))
        has_en = bool(re.search(r"[A-Za-z]", q))
        conds = []
        if has_ko:
            conds.append("search_ko LIKE :like")
            params["like"] = f"%{q}%"
        if has_en:
            conds.append("to_tsvector('english', search_en) @@ plainto_tsquery('english', :q)")
            params["q"] = q
        if not conds:  # 숫자·기호만
            conds.append("(search_ko LIKE :like OR search_en ILIKE :like)")
            params["like"] = f"%{q}%"
        where.append("(" + " OR ".join(conds) + ")")
        scope = SCOPE_BOTH if (has_ko and has_en) else (SCOPE_KO if has_ko else SCOPE_EN)

    w = (" WHERE " + " AND ".join(where)) if where else ""

    # 🔴 기본 정렬은 어디서나 최신순. relevance 는 선택지일 뿐이다 (PRD-05 FR-25).
    order = "collected_at DESC, id DESC"
    if sort == "relevance" and q:
        order = (
            "(CASE WHEN coalesce(title_ko, title_original) ILIKE :like2 THEN 3 ELSE 0 END) DESC, "
            "collected_at DESC, id DESC"
        )
        params["like2"] = f"%{q}%"

    params["limit"] = size
    params["offset"] = (page - 1) * size

    list_sql = f"SELECT {CARD_COLS} FROM contents{w} ORDER BY {order} LIMIT :limit OFFSET :offset"
    count_sql = f"SELECT count(*) FROM contents{w}"
    return list_sql, count_sql, params, scope


LOG_SEARCH = text(
    "INSERT INTO search_logs (query, result_count) VALUES (:q, :n)"
)  # 🔴 회원 식별자를 남기지 않는다 (PRD-02 FR-19)
