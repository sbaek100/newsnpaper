"""번역 프롬프트 — 초벌(1패스) + 검증·수정(2패스)

PRD-03 §8.1.2~8.1.4, FR-48~50(용어집), FR-72~80(보수적 후편집)
"""

import json
from pathlib import Path

GLOSSARY_PATH = Path(__file__).parent / "glossary.json"

LABELS = {
    "title": "제목",
    "summary": "요약",
    "Abstract": "초록",
    "Introduction": "서론",
    "Conclusion": "결론",
}


def load_glossary() -> list[dict]:
    with open(GLOSSARY_PATH, encoding="utf-8") as f:
        return json.load(f)["glossary"]


def glossary_block(glossary: list[dict], text: str) -> str:
    """본문에 등장하는 용어만 골라 넣는다. 전량을 넣으면 프롬프트가 길어진다."""
    low = text.lower()
    hits = [g for g in glossary if g["en"].lower() in low]
    if not hits:
        return ""
    lines = [
        f"- {g['en']} → {g['ko']}" + ("  (음차 유지)" if g["type"] == "transliteration" else "")
        for g in hits[:30]
    ]
    return "다음 용어는 반드시 아래 표기를 쓴다.\n" + "\n".join(lines) + "\n\n"


SYSTEM = (
    "너는 정보보안 분야 영한 번역가다. "
    "영어 원문을 자연스러운 한국어 기술 문서체로 옮긴다. "
    "번역문만 출력하고 설명·머리말·따옴표를 붙이지 않는다."
)

SYSTEM_VERIFY = (
    "너는 영한 번역 검수자다. "
    "원문과 초벌 번역을 받아 잘못된 곳만 고친다. "
    "고칠 것이 없으면 초벌을 그대로 출력한다. "
    "최종 번역문만 출력하고 무엇을 고쳤는지 설명하지 않는다."
)


def pass1(text: str, field: str, glossary: list[dict]) -> list[dict]:
    """초벌. --passes 값과 무관하게 항상 동일해야 한다."""
    label = LABELS.get(field.split(":")[-1], "본문")
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                f"{glossary_block(glossary, text)}"
                f"아래 {label}을(를) 한국어로 번역하라. 번역문만 출력한다.\n\n"
                f"{text}"
            ),
        },
    ]


def pass2(text: str, draft: str, field: str, glossary: list[dict]) -> list[dict]:
    """검증·수정. 보수적으로 동작해야 한다 (FR-72~74)."""
    label = LABELS.get(field.split(":")[-1], "본문")
    return [
        {"role": "system", "content": SYSTEM_VERIFY},
        {
            "role": "user",
            "content": (
                f"{glossary_block(glossary, text)}"
                f"[원문 {label}]\n{text}\n\n"
                f"[초벌 번역]\n{draft}\n\n"
                "다음 5가지만 고쳐라. 그 외에는 초벌을 그대로 둔다.\n"
                "1. 오역 — 원문과 뜻이 다른 곳\n"
                "2. 누락 — 원문에 있는데 빠진 내용\n"
                "3. 환각 — 원문에 없는데 생긴 내용\n"
                "4. 용어집 위반 — 위에 제시한 표기를 따르지 않은 곳\n"
                "5. 번역투 — 직역해서 어색한 곳을 한국어 기술 문서의 관용 표현으로\n\n"
                "원문에 없는 내용을 새로 추가하지 마라. 의미 보완·설명 추가를 하지 마라.\n"
                "고칠 것이 없으면 초벌을 그대로 출력하라."
            ),
        },
    ]
