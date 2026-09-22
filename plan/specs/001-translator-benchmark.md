# SPEC-001: 번역 모델 벤치마크

| 항목 | 값 |
|---|---|
| 근거 | PRD-03 §8.1 FR-42, architecture.md §4.1, roadmap.md 단계 1 |
| 목적 | Qwen2.5-7B-Instruct fp16이 이 서버 GPU에서 배치 부하를 감당하는지 **측정으로 판정** |
| 산출물 | `benchmarks/` 아래 스크립트·픽스처·결과 |
| 선행 조건 | 없음 (단계 0과 병행 가능) |

## 1. 왜 이걸 먼저 하는가

전체 계획에서 **유일하게 검증되지 않은 가정**이다. 결과에 따라 모델과 워커 구성이
바뀌고, 그러면 PRD-03 §8.1과 architecture.md §4를 고쳐야 한다.
`translator` 구현을 여기 결과 없이 시작하면 재작업이 난다.

## 2. 측정할 것

### 2.1 부하 단위 — 워커 1개가 배치 1회에 처리하는 양

배치 1회 = 뉴스 100건 + 논문 30건 → 번역 콜 320개 (PRD-03 §4.4).
워커 4개가 나눠 가지므로 **워커당 80콜.** 구성은 다음과 같다.

| 콜 종류 | 개수 | 입력 분량(대략) |
|---|---|---|
| 뉴스 제목 | 25 | 10~20 단어 |
| 뉴스 요약 | 25 | 40~80 단어 |
| 논문 제목 | 8 | 10~20 단어 |
| 논문 섹션 | 22 | Abstract 150~250 · Introduction 600~1000 · Conclusion 300~500 단어 |
| **합계** | **80** | |

논문 섹션 22개는 Abstract : Introduction : Conclusion을 **8 : 7 : 7**로 섞는다.

### 2.2 기록할 지표

| 지표 | 이유 |
|---|---|
| 모델 로딩 시간 (초) | PRD-03 FR-43 "배치 시각에만 기동" 정책의 비용 근거 |
| 80콜 총 소요 시간 | **판정의 주 지표** |
| 콜 종류별 평균·p50·p95 소요 | 어느 종류가 병목인지 |
| 출력 토큰/초 | 모델 교체 시 비교 기준 |
| VRAM 피크 (GPU별) | 2장 분산이 실제로 맞는지 |
| CPU 오프로딩 발생 여부 | 발생하면 측정이 무의미하다 (§5) |

## 3. 판정 기준

| 결과 | 조건 | 조치 |
|---|---|---|
| 🟢 통과 | 80콜 **≤ 60분** | Qwen2.5-7B-Instruct fp16 확정. 그대로 진행 |
| 🟡 조건부 | 60분 < t ≤ 4시간 | 7B 유지하되 수집 상한(PRD-03 FR-27)을 재검토 |
| 🔴 실패 | t > 4시간 · OOM · CPU 오프로딩 발생 | **Qwen2.5-3B-Instruct fp16 × GPU 1장 × 8워커**로 전환 |

> 배치 간격은 12시간이지만 그걸 다 쓰면 콘텐츠가 늦다.
> 실질 목표는 **1시간 이내**다.

3B로 전환할 경우 **같은 스크립트를 `--model`만 바꿔 재실행**할 수 있어야 한다.
이때 부하 단위는 워커당 40콜(8워커)이 된다 — `--calls` 인자로 조정 가능하게 할 것.

## 4. 만들 것

```
benchmarks/
├── README.md               실행 방법, 결과 해석
├── requirements.txt        transformers, accelerate, sentencepiece 등
├── translator_bench.py     본체
├── fixtures/
│   ├── news_titles.json        25건 이상
│   ├── news_summaries.json     25건 이상
│   ├── paper_titles.json       8건 이상
│   └── paper_sections.json     22건 이상 (name/text)
├── glossary.json           보안 용어집 (PRD-03 FR-48~50, 30개 내외로 시작)
└── results/                실행 결과 (gitignore)
```

### 4.1 `translator_bench.py` 인터페이스

```
python translator_bench.py \
    --model Qwen/Qwen2.5-7B-Instruct \
    --gpus 0,1 \
    --calls 80 \
    --out results/
```

| 인자 | 기본값 | 설명 |
|---|---|---|
| `--model` | `Qwen/Qwen2.5-7B-Instruct` | HF 모델 ID |
| `--gpus` | `0,1` | `CUDA_VISIBLE_DEVICES`에 넣을 값 |
| `--calls` | `80` | 총 콜 수. §2.1 비율을 유지하며 스케일 |
| `--out` | `results/` | 결과 저장 경로 |
| `--warmup` | `3` | 계측에서 제외할 예열 콜 수 |
| `--dry-run` | off | 모델을 로드하지 않고 픽스처·구성만 검증 |

### 4.2 출력

`results/{YYYYmmdd-HHMMSS}-{model-slug}.json` — 기계 판독용, §2.2 지표 전부.
`results/{같은 이름}.md` — 사람이 읽는 요약. **§3의 판정(🟢/🟡/🔴)을 첫 줄에 명시.**

번역 결과 샘플 20건(원문·번역 쌍)을 `.md`에 포함할 것 — 품질 육안 검토용.

## 5. 🔴 하드 제약 — 어기면 측정이 무효다

이 서버 GPU는 **NVIDIA TITAN Xp × 8, Pascal sm_61**이다. 최신 GPU를 전제한 설정은 실패한다.

| 제약 | 내용 |
|---|---|
| `bf16` **금지** | `torch.cuda.is_bf16_supported()`가 `True`를 반환하지만 **에뮬레이션**이다. 실측 5.7 TFLOPS로 fp32(10.4)의 절반. 반드시 `torch_dtype=torch.float16` |
| FlashAttention **금지** | sm_61 커널이 없어 `No available kernel`로 죽는다. `flash-attn`을 설치하지 말 것. `attn_implementation="sdpa"`를 쓰되 flash 백엔드를 끄고 math / mem-efficient로 폴백시킬 것 |
| 양자화 **금지** | 4bit/8bit 커널이 Pascal에서 불안정하다. 순수 fp16으로만 측정한다 |
| CUDA 버전 | torch 2.6.0+cu124 설치본을 **그대로 쓴다.** CUDA 13.x는 Pascal 지원이 삭제돼 GPU 8장이 전부 죽는다. `torch`를 재설치하지 말 것 |
| CPU 오프로딩 **금지** | `device_map`이 CPU로 흘리면 시간 측정이 무의미하다. 오프로딩이 감지되면 **에러로 중단**하고 그 사실을 보고할 것 |
| GPU 범위 | `--gpus`로 지정된 장만 쓴다. NUMA 그룹(0~3 / 4~7) 경계를 넘는 짝(예: `0,4`)은 경고를 띄울 것 |

### 5.1 환경

- 호스트 Python은 **3.10.12**, `torch 2.6.0+cu124`가 이미 있고 `transformers`는 **없다**
- 컨테이너는 아직 없다(단계 0 미완). **`benchmarks/.venv`에 venv를 만들어 실행**한다.
  `--system-site-packages`로 만들어 **기존 torch를 재사용**할 것 — 재설치 금지
- 모델 가중치는 약 15GB를 내려받는다. 디스크 여유 1.3T로 충분하다
- 실행 전 `nvidia-smi`로 대상 GPU가 유휴인지 확인하고, 사용 중이면 중단할 것

## 6. 번역 프롬프트

실제 `translator`가 쓸 것과 **같은 형태**여야 측정이 의미 있다.

- 시스템 프롬프트에 **용어집을 주입**한다 (PRD-03 FR-48)
- 용어집은 "음차 유지"(ransomware→랜섬웨어)와 "번역"(supply chain attack→공급망 공격)을 구분한다 (FR-49)
- 출력은 번역문만. 설명·머리말을 붙이지 않게 지시할 것
- `max_new_tokens`는 입력 길이에 비례해 잡되 상한을 둘 것 (섹션 번역이 폭주하지 않게)

## 7. 범위 밖 — 하지 말 것

- `translator` 워커 본체, 큐, DB 연동 → **단계 4**
- 수집 파이프라인, PDF 파싱 → 단계 3
- `docker-compose.yml`, Dockerfile → 단계 0
- 모델 파인튜닝·프롬프트 최적화 — 지금은 **있는 그대로 측정**하는 것이 목적이다
- 여러 모델 동시 비교 — 7B를 먼저 재고, 실패하면 그때 3B를 잰다

## 8. 검증 방법 (완료 판정)

- [ ] `python translator_bench.py --dry-run`이 모델 로드 없이 픽스처 구성을 검증한다
- [ ] 실행이 끝나면 `results/`에 `.json`과 `.md`가 한 쌍 생긴다
- [ ] `.md` 첫 줄에 🟢/🟡/🔴 판정이 보인다
- [ ] 로그 어디에도 `bfloat16`, `flash_attention`, `load_in_4bit`가 나타나지 않는다
- [ ] `nvidia-smi`로 확인한 VRAM 사용이 지정한 2장에만 잡힌다
- [ ] 번역 샘플 20건에서 `ransomware`가 "랜섬웨어"로 나온다 (용어집 동작 확인)
- [ ] `--model`만 바꿔 3B로 재실행이 된다

## 9. 보고할 것

작업 후 다음을 보고한다.

```
CHANGED: <생성·수정한 파일>
SUMMARY: <구현 요약 3줄 이내>
RESULT:  <🟢/🟡/🔴 판정과 80콜 소요 시간, 모델 로딩 시간, VRAM 피크>
CONCERNS: <제약 위반 가능성, 확신 없는 지점. 없으면 none>
```

**판정이 🔴이면 코드를 고치지 말고 그대로 보고하라.**
모델 전환은 PRD 수정을 동반하므로 사람이 결정한다.
