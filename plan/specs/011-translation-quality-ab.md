# SPEC-011: 번역 품질 A/B 평가 (EXAONE vs Qwen)

| 항목 | 값 |
|---|---|
| 근거 | PRD-03 §8.1(품질 우선 재정의), §8.7(품질 검증 체계) |
| 목적 | **실제 콘텐츠**로 두 모델의 번역 품질을 비교해 채택 모델을 정한다 |
| 선행 조건 | SPEC-001 하네스 (`benchmarks/translator_bench.py`) |
| 배경 | 1차 벤치마크는 무작위 단어 픽스처라 **품질을 전혀 측정하지 못했다** |

## 1. 왜 다시 하는가

사용자가 2026-09-23에 명시했다 — **"가장 중요한 것은 수집과 번역 품질"**.
기존 판정 기준은 속도뿐이었다. 그리고 1차 픽스처는 이런 것이었다:

> "Analysis network model method method results performance algorithm ransomware performance."

이걸로는 어떤 모델이 더 잘 번역하는지 알 수 없다. **실제 논문과 뉴스로 다시 잰다.**

비상업·개인 사용이 확인되어 **EXAONE의 NC 라이선스가 제약이 되지 않는다.**

## 2. 범위

| 만든다 | 만들지 않는다 |
|---|---|
| 실데이터 평가셋 수집 스크립트 | **모델 실행** — 오래 걸리므로 Claude가 `setsid`로 돌린다 |
| A/B 실행 하네스 (`--model` 두 번 돌려 짝 맞춤) | 채점 — Claude가 한다 |
| 블라인드 비교용 출력 포맷 | 프롬프트 튜닝 |
| 자동 이상 탐지 (형식·길이·한글비율) | |

> 🔴 **이 명세에서 모델을 실행하지 마라.** agy는 장시간 작업을 자기 백그라운드 태스크로
> 띄운 뒤 죽인다(`CLAUDE.md` §agy 통제 규칙). **코드 생성까지만 하고 보고하라.**

## 3. 평가셋 (PRD-03 FR-55~57)

`benchmarks/evalset/` 에 **고정 저장**한다. 모델이 바뀌어도 같은 입력을 쓴다.

| 종류 | 건수 | 출처 |
|---|---|---|
| 논문 | **5편** | arXiv **cs.CR** 최신. 제목 + Abstract + Introduction + Conclusion |
| 국제 뉴스 | **15건** | 보안 RSS (BleepingComputer, The Hacker News, Krebs 등). 제목 + 요약 |

| ID | 요구사항 |
|---|---|
| Q-1 | `benchmarks/fetch_evalset.py` — arXiv API와 RSS에서 실제 항목을 받아 저장한다 |
| Q-2 | arXiv는 `export.arxiv.org` API를 쓰고 **호출 간 3초 이상** 간격을 둔다 |
| Q-3 | 논문 Introduction/Conclusion은 PDF에서 추출한다. 추출 실패 항목은 **버리고 다른 논문으로 채운다** — 평가셋은 온전한 5편이어야 한다 |
| Q-4 | 받은 결과를 `evalset/papers.json`, `evalset/news.json`에 저장하고 **다시 받지 않는다** (재현성) |
| Q-5 | 각 항목에 `id`, `source_url`, 원문 텍스트를 담는다 |
| Q-6 | 스크립트는 **재실행 시 기존 파일을 덮어쓰지 않는다** (`--force` 없으면) |
| Q-7 | 수집한 PDF는 추출 후 삭제한다 |

## 4. A/B 하네스

| ID | 요구사항 |
|---|---|
| Q-8 | `benchmarks/quality_ab.py` — `--model`로 모델 하나를 받아 평가셋 전량을 번역하고 결과를 저장한다 |
| Q-9 | 출력은 `benchmarks/results/quality-{model-slug}.json` — 항목 `id`별로 원문·번역·소요시간·출력토큰수 |
| Q-10 | 두 모델 결과가 다 있으면 `quality_ab.py --compare A.json B.json` 로 **짝 맞춤 비교 파일**을 만든다 |
| Q-11 | 비교 파일은 두 종류를 낸다 — ①채점용(모델명 표시) ②**블라인드용(모델명을 A/B로 가리고 순서를 항목마다 무작위로 섞음, 정답 키는 별도 파일)** |
| Q-12 | SPEC-001의 프롬프트·용어집을 **그대로** 쓴다. 모델별로 프롬프트를 다르게 주지 마라 — 비교가 무의미해진다 |

### 4.1 자동 이상 탐지 (PRD-03 FR-61)

| ID | 요구사항 |
|---|---|
| Q-13 | 번역문의 **한글 문자 비율이 30% 미만**이면 `format_fail`로 표시 (번역이 안 된 것) |
| Q-14 | 원문 대비 길이가 **0.3배 미만 또는 3배 초과**면 `length_anomaly` |
| Q-15 | 번역문에 "다음은", "번역:", "Here is", "Translation:" 등 머리말이 있으면 `preamble_fail` |
| Q-16 | 용어집의 음차 유지 항목이 지켜지지 않으면 `glossary_miss`와 어긋난 용어를 기록 |
| Q-17 | 이 지표들을 결과 JSON에 담고, 요약 `.md`에 모델별 집계를 낸다 |

## 5. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| 모델 실행 금지 | §2 참조. 코드 생성까지만 |
| `bf16` 금지 | **EXAONE README가 `torch.bfloat16`을 예시로 쓴다. 반드시 `torch.float16`으로 바꿔라.** Pascal에서 bf16은 에뮬레이션이라 fp32의 절반 속도다 |
| EXAONE 특이사항 | `trust_remote_code=True`가 필요하다. 이를 코드에 명시하고 주석으로 이유를 남겨라 |
| FlashAttention 금지 | sm_61 커널 없음. SDPA는 math/mem-efficient로 폴백 |
| 양자화 금지 | 순수 fp16만 |
| 프롬프트 동일 | Q-12를 어기지 마라 |
| 평가셋 재수집 | Q-6을 어기지 마라. 매번 다른 데이터로 재면 비교가 안 된다 |
| 외부 심판 금지 | 외부 LLM API로 채점하지 마라 (PRD-03 FR-60) |

## 6. 검증 방법 (agy가 확인할 것)

- [ ] `python fetch_evalset.py` 로 `evalset/papers.json`(5편)·`news.json`(15건)이 생긴다
- [ ] 논문 5편 모두 Abstract·Introduction·Conclusion **3개 섹션이 온전하다**
- [ ] 재실행 시 덮어쓰지 않는다
- [ ] `papers_pdf/`가 비어 있다
- [ ] `python quality_ab.py --dry-run` 이 모델 로드 없이 구성을 검증한다
- [ ] `grep -rn "bfloat16\|bf16\|flash_attn\|load_in_4bit" benchmarks/` 가 **비어 있다**
- [ ] `trust_remote_code=True` 가 EXAONE 경로에 있다
- [ ] `--compare` 가 채점용·블라인드용 두 파일과 정답 키를 만든다
- [ ] 블라인드 파일에 모델명이 **한 번도 등장하지 않는다**

## 7. 실행은 Claude가 한다 (참고)

코드가 준비되면 Claude가 다음을 `setsid`로 돌린다. **agy는 실행하지 마라.**

```bash
python quality_ab.py --model Qwen/Qwen2.5-7B-Instruct           --gpus 0,1
python quality_ab.py --model LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct --gpus 2,3
python quality_ab.py --compare results/quality-Qwen*.json results/quality-EXAONE*.json
```

## 8. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
EVALSET: <논문 5편 제목 / 뉴스 15건 출처. 섹션 온전성>
VERIFY:  <§6 각 항목>
CONCERNS: <없으면 none>
```
