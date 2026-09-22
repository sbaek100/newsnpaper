# SPEC-013: 평가 하네스 결함 수정

| 항목 | 값 |
|---|---|
| 근거 | SPEC-011 실행 중 발견된 결함 6종, `plan/quality/translation-20260923.md` §6 |
| 목적 | 1차 A/B에서 드러난 **측정 도구 자체의 결함**을 고친다 |
| 선행 조건 | SPEC-011 (하네스가 존재해야 한다) |
| 후행 | 수정 후 A/B **재실행** (Claude가 `setsid`로 돌린다) |

## 1. 배경

1차 A/B는 EXAONE 3.7 / Qwen 2.1로 결론이 났지만, **측정 도구에 결함 6종**이 있어
절대 점수를 신뢰할 수 없다. 특히 자동 이상 탐지가 Qwen의 **중국어 혼입 5건 중 1건만**
잡았다 — 이대로 운영에 들어가면 깨진 번역이 그대로 화면에 나간다.

## 2. 🔴 결함 1 — 평가셋이 단어 중간에서 잘린다

`benchmarks/fetch_evalset.py` 약 128행:

```python
text = f"...Introduction: {intro[:2000]}...\n\nConclusion: {conc[:2000]}..."
```

| 증상 | 내용 |
|---|---|
| 단어 중간 절단 | 논문 5편 전부 Introduction이 정확히 2003자에서 끊김. `"...conditional next-token d"` (`distribution`이 `d`에서) |
| 거짓 `...` | 2000자보다 짧아 **안 잘린** Conclusion 2편에도 `...`을 붙여 잘린 것처럼 보이게 함 |

| ID | 요구사항 |
|---|---|
| F-1 | **절단 상한을 8,000자로 올린다.** 실제 Introduction은 600~1000단어(약 4,000~6,000자)라 대부분 온전히 들어간다 |
| F-2 | 상한을 넘으면 **문장 경계(`.` 뒤 공백)에서 자른다.** 단어 중간에서 자르지 마라 |
| F-3 | **실제로 잘렸을 때만** `…(생략)`을 붙인다. 안 잘렸으면 붙이지 마라 |
| F-4 | 각 섹션의 원본 길이와 절단 여부를 JSON에 `truncated: true/false`로 기록한다 |
| F-5 | 기존 `benchmarks/evalset/`을 **`--force`로 재생성**한다. 재생성 후 5편 모두 3섹션이 온전한지 확인한다 |

## 3. 🔴 결함 2 — 자동 이상 탐지가 붕괴를 못 잡는다

현재 탐지는 `format_fail`(한글 비율 30% 미만), `length_anomaly`, `preamble_fail`,
`glossary_miss` 4종뿐이다. **Qwen의 중국어 혼입 5건 중 1건만 잡았다.**
번역문 대부분이 한국어라 한글 비율 30%를 통과해버린 것이다.

| ID | 요구사항 |
|---|---|
| F-6 | **`cjk_contamination`** 신설 — 한중일 통합 한자(`U+4E00–U+9FFF`)가 **1자라도** 있으면 탐지. 한글(`U+AC00–U+D7AF`)과 구분할 것 |
| F-7 | **`cyrillic_contamination`** 신설 — 키릴 문자(`U+0400–U+04FF`) 1자라도 |
| F-8 | **`mojibake`** 신설 — 치환 문자(`U+FFFD`, `�`) 1자라도 |
| F-9 | **`repetition`** 신설 — 같은 문장(30자 이상)이 3회 이상 반복되면 탐지 |
| F-10 | `format_fail` 임계를 한글 비율 **30% → 45%** 로 올린다 |
| F-11 | 이 4종은 **치명(critical)** 으로 분류하고, 요약에서 일반 이상과 **구분해 표시**한다 |
| F-12 | 탐지된 위치(문자 인덱스와 앞뒤 40자)를 함께 기록해 확인이 쉽게 한다 |

**검증** — 수정 후 기존 Qwen 결과 JSON에 이 탐지를 돌려 **중국어 혼입 5건이 전부 잡히는지** 확인하라.
5건을 못 잡으면 탐지가 아직 부족한 것이다.

## 4. 결함 3 — `--dry-run`이 조용히 아무것도 안 한다

`main()`이 `if args.compare ... elif args.model ... else: print_help()` 구조라
`--model` 없이 `--dry-run`만 주면 **help만 찍고 exit 0**으로 끝난다. 검증한 줄 알고 넘어간다.

| ID | 요구사항 |
|---|---|
| F-13 | `--dry-run`을 `--model` 없이 줘도 **평가셋·용어집·프롬프트 구성을 검증**하고 결과를 출력한다 |
| F-14 | 검증할 수 없는 상태면 **exit 1**로 명확히 실패한다. 조용히 exit 0 하지 마라 |

## 5. 결함 4 — 저장소 루트에서만 동작한다

`benchmarks/glossary.json`, `benchmarks/evalset/*.json`을 상대경로로 참조해
`cd benchmarks && python quality_ab.py`로 실행하면 `FileNotFoundError`로 죽는다.

| ID | 요구사항 |
|---|---|
| F-15 | 모든 데이터 경로를 `Path(__file__).parent` 기준으로 해석한다. **어느 디렉토리에서 실행해도 동작해야 한다** |
| F-16 | `fetch_evalset.py`, `quality_ab.py`, `translator_bench.py` 셋 다 적용 |

## 6. 결함 5 — `requirements.txt` 누락

`fetch_evalset.py`가 쓰는 `requests`, `feedparser`, `pypdf`가 빠져 있다.
현재 venv에는 설치돼 있어 동작하지만 venv를 새로 만들면 재현되지 않는다.

| ID | 요구사항 |
|---|---|
| F-17 | 누락 의존성을 `benchmarks/requirements.txt`에 추가한다 |
| F-18 | **`torch`를 넣지 마라** — 기존 2.6.0+cu124를 재사용해야 한다 |

## 7. 🔴 결함 6 — 프롬프트가 출력 형식을 강제하지 않는다

EXAONE이 `제목:` / `요약:` 라벨을 6건 이상에서 임의로 누락했다.
**모델 탓이 아니라 프롬프트가 형식을 명시하지 않은 탓이다.**

| ID | 요구사항 |
|---|---|
| F-19 | 프롬프트에 **출력 형식을 명시**한다 — 입력에 `Title:`이 있으면 `제목:`으로, `Summary:`는 `요약:`으로, `Abstract:`/`Introduction:`/`Conclusion:`은 각각 대응 라벨로 시작할 것 |
| F-20 | "번역문만 출력하고 설명·머리말을 붙이지 말 것"을 명시한다 |
| F-21 | 🔴 **두 모델에 완전히 같은 프롬프트를 쓴다.** 모델별로 다르게 주면 비교가 무효다 |
| F-22 | 용어집 주입 방식은 바꾸지 마라 — 이번 수정 범위 밖이다 |

## 8. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| 모델 실행 금지 | agy는 **코드 수정과 평가셋 재수집까지만**. 모델 로딩·번역은 Claude가 `setsid`로 돌린다 (`CLAUDE.md` §agy 통제 규칙) |
| 프롬프트 동일 | F-21을 어기지 마라 |
| 통과선 변경 금지 | PRD-03 §8.1.2의 품질 4.0 / 속도 4시간을 코드에서 바꾸지 마라 |
| `bf16`·FlashAttention·양자화 금지 | Pascal sm_61. 기존 설정을 유지하라 |
| 1차 결과 보존 | `benchmarks/results/quality-*.json` 2개를 **지우지 마라.** 비교 근거다 |
| 채점 자동화 금지 | 품질 점수를 코드가 매기게 하지 마라. 탐지는 기계적 이상만 (PRD-03 FR-58) |

## 9. 검증 방법

- [ ] `python benchmarks/fetch_evalset.py --force` 후 논문 5편의 Introduction이 **2003자가 아니다**
- [ ] 절단된 섹션이 **문장 경계**에서 끝난다 (단어 중간 아님)
- [ ] 안 잘린 섹션에 `…(생략)`이 **붙지 않는다**
- [ ] JSON에 `truncated` 플래그가 있다
- [ ] 기존 Qwen 결과에 새 탐지를 돌리면 **중국어 혼입 5건이 전부** 잡힌다
- [ ] 키릴(news-14)·mojibake(news-4, news-8)도 잡힌다
- [ ] 반복(news-4의 3회 반복 문단)이 잡힌다
- [ ] `cd /tmp && python /home/infosec/mypage/benchmarks/quality_ab.py --dry-run` 이 동작한다
- [ ] `--dry-run`이 구성을 실제로 검증하고, 실패 시 exit 1
- [ ] `requirements.txt`에 `requests`·`feedparser`·`pypdf`가 있고 `torch`는 없다
- [ ] 프롬프트에 출력 형식 지시가 있고, **모델 분기 없이 하나**다
- [ ] `grep -rn "bfloat16\|flash_attn\|load_in_4bit" benchmarks/ --exclude-dir=.venv*` 가 주석 외 비어 있다

## 10. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
DETECT:  <기존 Qwen 결과에 새 탐지를 돌린 결과 — 중국어 5건/키릴 1건/mojibake 2건/반복이
          각각 잡혔는지. 못 잡은 게 있으면 명시>
EVALSET: <재수집 후 논문 5편의 섹션별 글자수와 truncated 플래그>
VERIFY:  <§9 각 항목>
CONCERNS: <없으면 none>
```

**새 탐지가 중국어 혼입 5건을 다 못 잡으면 고쳤다고 보고하지 마라.**
그게 이 수정의 핵심이다.
