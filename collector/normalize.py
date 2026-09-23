"""URL 정규화 · 언어 판별 · 키워드 매칭 — PRD-03 §3, §4.2"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 기본 수집 키워드 (PRD-03 §3.1)
KEYWORDS = {
    "보안": ["보안", "security"],
    "해킹": ["해킹", "hacking", "hacker", "hacked"],
    "사이버": ["사이버", "cyber"],
    "AI": ["AI", "인공지능", "artificial intelligence", "machine learning", "LLM"],
}

# 추적 파라미터 (PRD-03 C-14)
_TRACKING = re.compile(
    r"^(utm_|fbclid$|gclid$|mc_cid$|mc_eid$|igshid$|ref$|ref_src$|source$|cmpid$)"
)

_HANGUL = re.compile(r"[가-힯]")


def normalize_url(url: str) -> str:
    """추적 파라미터 제거, 소문자화, 기본 포트·말미 슬래시 정리."""
    if not url:
        return url
    p = urlsplit(url.strip())
    scheme = (p.scheme or "https").lower()
    host = p.hostname.lower() if p.hostname else ""
    if host.startswith("www."):
        host = host[4:]
    # 기본 포트 제거
    if p.port and not ((scheme == "http" and p.port == 80) or (scheme == "https" and p.port == 443)):
        host = f"{host}:{p.port}"
    query = urlencode(
        [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not _TRACKING.match(k.lower())]
    )
    path = p.path.rstrip("/") or "/"
    return urlunsplit((scheme, host, path, query, ""))


def hangul_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return len(_HANGUL.findall(text)) / len(letters)


def detect_language(text: str) -> str:
    """한글 비율 휴리스틱. 외부 언어감지 API를 쓰지 않는다 (PRD-03 C-32)."""
    return "ko" if hangul_ratio(text) >= 0.3 else "en"


def match_keywords(text: str) -> list[str]:
    """매칭된 기본 키워드 목록 (PRD-03 FR-33·34). 여러 개면 전부 반환."""
    low = (text or "").lower()
    return [
        name
        for name, variants in KEYWORDS.items()
        if any(v.lower() in low for v in variants)
    ]


def clean_html(raw: str) -> str:
    """RSS description 의 태그·엔티티 제거."""
    if not raw:
        return ""
    import html

    txt = re.sub(r"<[^>]+>", " ", raw)
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()
