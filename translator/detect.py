"""번역 이상 탐지 — PRD-03 §8.7.1

치명 3종은 DB 기록 전 재시도, 경고는 기록만 한다.
평가 도구(benchmarks/quality_ab.py)의 반복 탐지에는 오탐이 있다.
여기서는 §8.7.2 의 정정된 규칙을 쓴다.
"""

import re

CJK = re.compile(r"[一-鿿]")  # 한중일 한자 (한글 U+AC00~U+D7AF 와 별개)
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
MOJIBAKE = re.compile("�")
HANGUL = re.compile(r"[가-힯]")
PREAMBLE = re.compile(
    r"^\s*(다음은|아래는|번역\s*[:：]|번역문\s*[:：]|Here is|Translation\s*:)", re.I
)

CRITICAL = {"cjk_contamination", "cyrillic_contamination", "mojibake"}


def _hangul_ratio(t: str) -> float:
    letters = [c for c in t if c.isalpha()]
    return len(HANGUL.findall(t)) / len(letters) if letters else 0.0


def _repetition(t: str) -> bool:
    """§8.7.2 — '100자 이상 2회' 또는 '30자 이상 3회' 의 OR.

    30자 2회로 잡으면 논문 서론·결론의 자연스러운 어구 반복이 오탐된다.
    """
    for span, times in ((100, 2), (30, 3)):
        if len(t) < span * times:
            continue
        for i in range(0, len(t) - span, max(span // 2, 1)):
            chunk = t[i : i + span]
            if not chunk.strip():
                continue
            if t.count(chunk) >= times:
                return True
    return False


def check(translated: str, original: str = "", glossary: list[dict] | None = None) -> dict:
    """탐지 결과 dict. 값은 탐지 위치와 앞뒤 문맥(FR-61c)."""
    found: dict[str, str] = {}

    for name, pat in (
        ("cjk_contamination", CJK),
        ("cyrillic_contamination", CYRILLIC),
        ("mojibake", MOJIBAKE),
    ):
        m = pat.search(translated)
        if m:
            s = max(0, m.start() - 40)
            found[name] = translated[s : m.end() + 40]

    if _repetition(translated):
        found["repetition"] = ""
    if _hangul_ratio(translated) < 0.45:
        found["format_fail"] = f"hangul={_hangul_ratio(translated):.2f}"
    if original:
        ratio = len(translated) / max(len(original), 1)
        if ratio < 0.3 or ratio > 3.0:
            found["length_anomaly"] = f"ratio={ratio:.2f}"
    if PREAMBLE.search(translated):
        found["preamble_fail"] = translated[:40]

    for g in glossary or []:
        if g.get("type") != "transliteration":
            continue
        if g["en"].lower() in (original or "").lower() and g["ko"] not in translated:
            found.setdefault("glossary_miss", "")
            found["glossary_miss"] += f"{g['en']}→{g['ko']} "

    return found


def has_critical(found: dict) -> bool:
    return bool(CRITICAL & set(found))


def strip_preamble(text: str) -> str:
    """머리말·구분선·감싼 따옴표 제거. 모델이 지시를 어겼을 때의 후처리."""
    t = text.strip()
    lines = [ln for ln in t.split("\n")]
    # 앞뒤 구분선(--- , ```)
    while lines and lines[0].strip().strip("-`").strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip().strip("-`").strip() == "":
        lines.pop()
    # 머리말 한 줄
    if len(lines) > 1 and PREAMBLE.search(lines[0]):
        lines.pop(0)
    t = "\n".join(lines).strip()
    # 전체를 감싼 따옴표
    if len(t) > 1 and t[0] in "\"'\u201c\u2018" and t[-1] in "\"'\u201d\u2019":
        t = t[1:-1].strip()
    return t
