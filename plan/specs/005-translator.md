# SPEC-005: 번역 워커

| 항목 | 값 |
|---|---|
| 근거 | roadmap.md 단계 4, PRD-03 §5·§8, architecture.md §4·§7.3 |
| 목적 | 큐를 소비해 온프레미스 LLM으로 번역하고 DB에 쓴다 |
| 선행 조건 | **SPEC-001 벤치마크 결과** (모델·워커 구성이 여기서 정해진다) + SPEC-004 (큐가 차야 한다) |
| 후행 | SPEC-006 API |

## 1. 🔴 시작 전 확인

**SPEC-001 벤치마크 판정을 먼저 읽어라.** `benchmarks/results/`의 최신 `.md`다.

| 판정 | 구성 |
|---|---|
| 🟢 / 🟡 | Qwen2.5-7B-Instruct fp16, **워커 4개 × GPU 2장** (0+1 / 2+3 / 4+5 / 6+7) |
| 🔴 | Qwen2.5-3B-Instruct fp16, **워커 8개 × GPU 1장** |

판정을 확인할 수 없으면 **작업을 멈추고 보고하라.** 추측으로 진행하지 마라.

## 2. 범위

| 만든다 | 만들지 않는다 |
|---|---|
| 큐 소비 워커 (`FOR UPDATE SKIP LOCKED`) | 수집 (→ SPEC-004) |
| 모델 로드·번역 실행 | API (→ SPEC-006) |
| 용어집 주입 프롬프트 | 모델 파인튜닝 |
| 재시도 + 지수 백오프 | 자체 추론 서버(vLLM 등) |
| 워커 기동/종료 스크립트 | |

## 3. 큐 소비 (architecture.md §7.3)

```sql
SELECT id FROM translation_jobs
 WHERE status = 'pending'
 ORDER BY created_at
 LIMIT 8
 FOR UPDATE SKIP LOCKED;
```

| ID | 요구사항 |
|---|---|
| T-1 | `FOR UPDATE SKIP LOCKED`로 워커 간 경합을 처리한다. **메시지 브로커를 도입하지 마라** |
| T-2 | 폴링 간격 2초 (architecture.md A-4) |
| T-3 | **큐가 비면 워커를 종료한다** (PRD-03 FR-43 — 배치 시각에만 기동) |
| T-4 | 집어간 job은 즉시 `status='running'`, `started_at` 기록 |
| T-5 | 워커가 죽어 `running`으로 남은 job은 다음 기동 시 회수한다 (`started_at`이 N분 이전이면 `pending`으로 되돌림) |

## 4. 번역 실행

| ID | 요구사항 |
|---|---|
| T-6 | 번역 결과를 `contents`의 해당 필드(`title_ko` / `summary_ko` / `sections[].textKo`)에 쓴다 |
| T-7 | `sections`는 JSONB이므로 **해당 섹션만 갱신**한다. 통째 덮어쓰면 동시 작업이 서로를 지운다 |
| T-8 | 한 콘텐츠의 모든 job이 끝나면 `translation_status='done'` |
| T-9 | 하나라도 영구 실패하면 `'failed'` — 원문을 노출한다 (FR-9) |
| T-10 | **원문을 지우지 마라** (FR-8). `title_original`·`textOriginal`은 그대로 둔다 |

### 4.1 프롬프트 · 용어집 (FR-48~50)

| ID | 요구사항 |
|---|---|
| T-11 | 시스템 프롬프트에 용어집을 주입한다 |
| T-12 | 용어집은 **음차 유지**(ransomware→랜섬웨어)와 **번역**(supply chain attack→공급망 공격)을 구분한다 (FR-49) |
| T-13 | 용어집은 설정 파일(`config/glossary.json`)로 둔다. 코드에 박지 마라 |
| T-14 | 초기 50개 내외로 시작한다 (FR-50). SPEC-001의 `benchmarks/glossary.json`을 출발점으로 쓸 수 있다 |
| T-15 | 출력은 **번역문만**. "다음은 번역입니다" 같은 머리말이 붙으면 제거하는 후처리를 둔다 |
| T-16 | `max_new_tokens`는 입력 길이에 비례하되 상한을 둔다 — 섹션 번역이 폭주하지 않게 |

## 5. 재시도 (FR-45~47)

| ID | 요구사항 |
|---|---|
| T-17 | 최대 **3회 재시도**, 지수 백오프 **10s / 60s / 300s** |
| T-18 | 3회 실패하면 `status='failed'` 확정. **다음 배치에서 재시도하지 않는다** (FR-46) |
| T-19 | `last_error`에 마지막 에러를 남긴다 (스택트레이스 전체 말고 요약) |
| T-20 | 관리자가 수동 재시도할 수 있게 `status`를 `pending`으로 되돌리는 진입점을 둔다 (FR-47) |

## 6. 워커 기동

| ID | 요구사항 |
|---|---|
| T-21 | `CUDA_VISIBLE_DEVICES`로 GPU를 할당한다. 워커 인덱스 → GPU 매핑을 설정으로 둔다 |
| T-22 | **NUMA 그룹(0~3 / 4~7) 경계를 넘는 짝을 만들지 마라** (FR-40). 잘못된 조합이면 기동 거부 |
| T-23 | 기동 실패 시 재시도하고, **3회 실패하면 배치를 실패로 기록한다** (FR-44) |
| T-24 | `docker compose --profile batch up translator` 로 뜬다 |
| T-25 | 모델 로딩 시간을 로그에 남긴다 (기동 정책 비용 추적) |

## 7. 🔴 하드 제약 — Pascal sm_61

이 서버 GPU는 **NVIDIA TITAN Xp × 8, Pascal sm_61**이다.

| 제약 | 내용 |
|---|---|
| `bf16` **금지** | `torch.cuda.is_bf16_supported()`가 `True`를 반환하지만 **에뮬레이션**이다. fp32의 절반 속도. 반드시 `torch.float16` (FR-41) |
| FlashAttention **금지** | sm_61 커널이 없어 `No available kernel`로 죽는다. `flash-attn`을 설치하지 마라. SDPA는 math / mem-efficient로 폴백시켜라 (FR-41) |
| 양자화 **금지** | Pascal에서 4bit/8bit 커널이 불안정하다. 순수 fp16만 |
| CUDA | 베이스 이미지 `nvidia/cuda:12.1.1-*`. **13.x는 Pascal 지원이 삭제돼 GPU 8장이 전부 죽는다** |
| CPU 오프로딩 | `device_map`이 CPU로 흘리면 속도가 무너진다. 감지되면 에러로 중단하라 |
| 외부 API | **번역을 외부로 보내지 마라** (FR-13). OpenAI·Gemini·Claude API 호출 금지 |

## 8. 검증 방법

- [ ] SPEC-001 판정을 읽고 그에 맞는 모델·워커 수로 구성했다
- [ ] 큐에 job이 있을 때 워커가 집어간다
- [ ] 워커 2개를 동시에 띄워도 **같은 job을 두 번 처리하지 않는다** (T-1)
- [ ] 큐가 비면 워커가 스스로 종료한다 (T-3)
- [ ] 논문 섹션 3개를 각각 번역해도 `sections` JSONB의 다른 섹션이 지워지지 않는다 (T-7)
- [ ] `ransomware`가 "랜섬웨어"로 번역된다 (용어집 동작)
- [ ] 번역 후에도 `title_original`이 남아 있다 (T-10)
- [ ] 일부러 실패시키면 3회 재시도 후 `failed`가 된다
- [ ] `grep -rE "bfloat16|bf16|flash_attn|load_in_4bit|load_in_8bit" translator/` 결과가 **비어 있다**
- [ ] `nvidia-smi`로 지정한 GPU에만 메모리가 잡힌다
- [ ] GPU 짝을 `0,4`로 주면 기동을 거부한다 (T-22)

## 9. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
CONFIG:  <SPEC-001 판정 / 채택한 모델 / 워커 수 / GPU 매핑>
VERIFY:  <§8 각 항목>
PERF:    <실제 큐 소비 속도 — job/분, 모델 로딩 시간>
CONCERNS: <없으면 none>
```

**SPEC-001 판정을 읽을 수 없으면 아무것도 만들지 말고 그 사실만 보고하라.**
