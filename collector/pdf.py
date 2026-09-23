"""논문 PDF 텍스트 추출 + 섹션 휴리스틱 — PRD-03 §5.4, §5.7

CPU 바운드라 ProcessPoolExecutor 에서 실행한다 (architecture.md §4.5.3).
이벤트 루프에서 직접 돌리지 마라 (A-6).
"""

import re

MAX_FULLTEXT = 200_000  # PRD-03 FR-52
MIN_SECTION = 200  # FR-19: 너무 짧으면 실패
MAX_SECTION = 50_000  # FR-19: 너무 길면 실패

# FR-17: 섹션 제목 변형을 다중 패턴으로
_HEAD = r"(?:^|\n)\s*(?:\d+\.?\s*|[IVX]+\.?\s*)?"
PATTERNS = {
    "Abstract": re.compile(_HEAD + r"(?:ABSTRACT|Abstract)\s*[\.:]?\s*\n", re.M),
    "Introduction": re.compile(
        _HEAD + r"(?:INTRODUCTION|Introduction|Background and Motivation)\s*[\.:]?\s*\n", re.M
    ),
    "Conclusion": re.compile(
        _HEAD
        + r"(?:CONCLUSIONS?|Conclusions?|Concluding Remarks|"
        r"Discussion and Conclusions?|Conclusions? and Future Work)\s*[\.:]?\s*\n",
        re.M,
    ),
}
# 섹션 끝을 잡기 위한 다음 제목 후보
_NEXT_HEAD = re.compile(
    _HEAD
    + r"(?:[A-Z][A-Za-z ]{2,40}|REFERENCES|References|ACKNOWLEDG\w+|Acknowledg\w+)\s*\n",
    re.M,
)


def extract_text(pdf_bytes: bytes) -> str:
    """PyMuPDF 로 텍스트 추출. 2단 조판을 고려해 블록 정렬한다 (FR-18)."""
    import fitz  # PyMuPDF

    out = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            # sort=True 가 컬럼 순서를 왼쪽→오른쪽, 위→아래로 정렬한다
            out.append(page.get_text("text", sort=True))
    text = "\n".join(out)
    text = re.sub(r"-\n(?=[a-z])", "", text)  # 하이픈 줄바꿈 복원
    return re.sub(r"\n{3,}", "\n\n", text)


def _slice_section(text: str, start: int) -> str:
    m = _NEXT_HEAD.search(text, start + 40)
    end = m.start() if m else min(len(text), start + MAX_SECTION)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def extract_sections(text: str) -> tuple[dict[str, str], str]:
    """(섹션 dict, 상태) 반환. 상태 = full | abstract_only | failed"""
    found: dict[str, str] = {}
    for name, pat in PATTERNS.items():
        m = pat.search(text)
        if not m:
            continue
        body = _slice_section(text, m.end())
        if MIN_SECTION <= len(body) <= MAX_SECTION:  # FR-19
            found[name] = body

    if len(found) == 3:
        return found, "full"
    if "Abstract" in found:
        return {"Abstract": found["Abstract"]}, "abstract_only"
    return {}, "failed"


def parse_pdf(pdf_bytes: bytes, abstract_fallback: str = "") -> dict:
    """프로세스 풀에서 실행되는 진입점. 예외를 밖으로 내보내지 않는다."""
    try:
        text = extract_text(pdf_bytes)
    except Exception as e:  # noqa: BLE001
        return {"sections": {}, "status": "failed", "full_text": "", "error": str(e)[:200]}

    sections, status = extract_sections(text)
    if status == "failed" and abstract_fallback:  # FR-15 폴백
        sections, status = {"Abstract": abstract_fallback}, "abstract_only"

    return {
        "sections": sections,
        "status": status,
        "full_text": text[:MAX_FULLTEXT],  # FR-52
        "error": None,
    }
