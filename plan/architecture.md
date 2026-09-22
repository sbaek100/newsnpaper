# 시스템 아키텍처

| 항목 | 값 |
|---|---|
| 상태 | **Confirmed** (2026-09-23) |
| 최종 수정 | 2026-09-23 |
| 관련 문서 | PRD-01 ~ PRD-06 |

## 1. 배포 형태 (2026-09-23 확정)

**Docker Compose 기반 전체 온프레미스 구성.** 외부 클라우드에 의존하지 않는다.

기존 `frontend/vite.config.js`에 컨테이너 볼륨 마운트를 전제한
`watch.usePolling: true`가 이미 설정되어 있어 이 방향과 일치한다.

⚠️ **완전 폐쇄망은 불가능하다.** 수집 파이프라인이 arXiv·Semantic Scholar·RSS·뉴스 API로
아웃바운드 호출을 해야 한다(PRD-03 §4.1). 허용 아웃바운드 목록 정의는 PRD-02의 몫이다.
번역은 온프레미스에서만 수행되므로 **콘텐츠 자체는 외부로 나가지 않는다**(PRD-03 FR-13).

## 2. 구성 요소

| 서비스 | 역할 | 상태 |
|---|---|---|
| `proxy` | Caddy — 단일 오리진으로 `/api`와 프론트를 묶는다 | 확정 (§7.4) |
| `frontend` | React 18 + Vite 5 + react-router-dom 6 | 확정 · 코드 없음 |
| `backend` | FastAPI — 조회·검색·인증 API | 확정 (§7.1) |
| `db` | PostgreSQL 16 + `pg_bigm` — 콘텐츠·번역·색인·회원 | 확정 (§2.1) |
| `collector` | Python + APScheduler, 09:00/21:00 배치 | 확정 (§7.1) |
| `translator` | PyTorch 번역 워커 × 4 (GPU 2장씩) | 확정 · **모델 벤치마크 대기** |

### 2.1 검색 서비스를 따로 두지 않는다 (2026-09-23 확정)

PRD-05 §6.1에서 **PostgreSQL + `pg_bigm` 단일 DB**로 확정됐다.
OpenSearch/Meilisearch 같은 별도 검색 컨테이너를 추가하지 않는다.

근거 — 수집 상한이 일 260건(PRD-03 §4.4)이다. 이 규모에 JVM 2~4GB 상주는 과잉이고,
별도 엔진은 DB↔색인 동기화 코드를 따로 요구한다. 품질이 부족하면 **같은 DB 안에서**
`mecab-ko` 확장을 추가하는 경로를 남겨 둔다.

> `pg_bigm`은 기본 PostgreSQL 이미지에 없다. **커스텀 이미지를 빌드하거나
> 확장이 포함된 이미지를 써야 한다.** 이것이 db 서비스의 첫 구현 과제다.

## 3. 데이터 흐름

```
 ┌─ arXiv API ────┐
 ├─ Semantic Sch. ┤
 ├─ RSS 피드      ┤──▶ collector ──▶ dedup ──▶ 번역 큐 ──▶ translator ×8 (GPU)
 └─ 뉴스 API ─────┘      (하루 2회)   (URL/DOI)              │
                                                            ▼
                                            db (PostgreSQL + pg_bigm)
                                              · 콘텐츠 + 번역 + 색인
                                              · 회원 / 구독 키워드
                                                            │
                                                            ▼
                                                         backend API
                                                            │
                                                            ▼
                                                         frontend
                                    메인 / 논문 상세 / 검색 결과 / 카테고리 목록
```

**논문 PDF 경로** — `collector`가 PDF를 내려받아 텍스트를 추출하고,
3개 섹션(번역 대상)과 전문(`fullTextOriginal`, 색인 전용)을 분리해 DB에 넣는다.
PDF 원본 보관 여부는 미결(§7).

## 4. 번역 워커 구성 (GPU) — 2026-09-23 확정

**워커 1개당 GPU 2장, 총 4워커** (PRD-03 §8.1).

| 워커 | GPU | NUMA |
|---|---|---|
| `translator-0` | 0, 1 | 그룹 A |
| `translator-1` | 2, 3 | 그룹 A |
| `translator-2` | 4, 5 | 그룹 B |
| `translator-3` | 6, 7 | 그룹 B |

- **왜 1장씩 8워커가 아닌가** — Qwen2.5-7B fp16은 가중치만 약 14GB로 12GB 1장에
  들어가지 않는다. 4비트 양자화로 1장에 넣는 경로는 Pascal(sm_61)에서 커널 지원이
  불안정해 검증 비용이 크다
- **NUMA 경계를 넘지 않는다** — 짝이 모두 같은 그룹(0~3 / 4~7) 안에 있다.
  그룹 간 전송은 호스트 메모리를 경유해 느리다
- 워커별 `CUDA_VISIBLE_DEVICES=0,1` 식으로 2장씩 할당
- 컨테이너에 `deploy.resources.reservations.devices` 또는 `runtime: nvidia` 필요

### 4.1 부하 산정 (PRD-03 §4.4)

| 항목 | 값 |
|---|---|
| 배치 1회 | 뉴스 100건 · 논문 30건 |
| 배치당 번역 콜 | 뉴스 100×2 + 논문 30×4 = **320콜** |
| 4워커 분담 | **워커당 80콜** |

`fullTextOriginal`은 번역 대상이 아니므로 이 계산에 포함되지 않는다.

> ⚠️ **PRD-03 FR-42 벤치마크가 유일하게 남은 검증 게이트다.**
> 워커당 80콜이 배치 간격(12시간) 안에 끝나지 않으면
> Qwen2.5-3B-Instruct fp16 × GPU 1장 × 8워커로 전환한다.

### 4.2 기동 정책 — 배치 시각에만

상시 기동하지 않는다. 이 서버는 다른 실험에도 쓰이므로 GPU를 하루 종일 점유할 수 없다.
모델 로딩 비용(회당 1~2분)은 하루 2회면 무시할 만하다 (PRD-03 FR-43).

## 5. GPU 하드 제약 (변경 불가)

- NVIDIA TITAN Xp × 8 (각 12GB, **Pascal sm_61**), Docker GPU 패스스루 동작 확인됨
- **`bf16` 사용 금지** — `is_bf16_supported()`가 True를 반환하지만 에뮬레이션이다.
  실측 5.7 TFLOPS로 fp32(10.4)의 절반. 기본 `fp32`, VRAM이 부족할 때만 `fp16`
- **FlashAttention 사용 불가** — sm_61 커널이 없어 `No available kernel`로 죽는다.
  SDPA는 math / mem-efficient 백엔드로 폴백시킬 것
- **CUDA 12.1 / cuDNN 9.10.2 고정** — 상위 버전은 Pascal 지원이 삭제되어 GPU 8장이
  전부 무용지물이 된다. 컨테이너 베이스 이미지 선택 시 반드시 확인
- **모델 크기 상한** — 12GB 제약상 7B급. 양자화 시 1장, fp16은 2장 필요

## 6. 프론트엔드 라우팅 (2026-09-23 추가)

PRD-04 §10(논문 상세)과 PRD-06(검색 결과·목록)이 확정되면서 **메인 1페이지 구조가
아니게 되었다.** 라우팅이 필요하다.

| 경로 | 화면 | 문서 |
|---|---|---|
| `/` | 메인 (3D Hero + 그리드) | PRD-04 |
| `/papers/:id` | 논문 상세 (3섹션 번역 + 원문 토글) | PRD-04 §10 |
| `/search` | 검색 결과 | PRD-06 §4.2 |
| `/news/international`, `/news/domestic`, `/papers` | 카테고리 목록 | PRD-06 §4.3 |

> ⚠️ `frontend/package.json`에 **라우터가 없다.** `react-router-dom` 도입이 필요하다.
> PRD-04 §6의 기술 스택 표에도 빠져 있다.

## 7. 스택 확정 (2026-09-23)

### 7.1 백엔드 — Python / FastAPI로 통일

| 서비스 | 스택 |
|---|---|
| `backend` | **Python 3.11 + FastAPI + SQLAlchemy 2.0 + Pydantic v2** |
| `collector` | Python 3.11 (`httpx`, `feedparser`, `PyMuPDF`) + APScheduler |
| `translator` | Python 3.11 + PyTorch 2.6 + Transformers |
| `db` | PostgreSQL 16 + `pg_bigm` (커스텀 이미지) |
| `frontend` | React 18 + Vite 5 + **react-router-dom 6** |

**왜 Python 통일인가** — `collector`는 PDF 파싱(PyMuPDF), `translator`는 GPU
추론(PyTorch)이 필수라 이미 Python이다. `backend`만 Node로 두면 모델·스키마 정의가
두 언어로 갈라지고, SQLAlchemy 모델을 collector와 공유할 수 없다.
세 서비스가 같은 `models/` 패키지를 쓰는 편이 훨씬 싸다.

| ID | 요구사항 |
|---|---|
| A-1 | `backend`·`collector`·`translator`는 공통 `shared/` 패키지(모델·설정·DB 세션)를 공유한다 |
| A-2 | `translator`만 CUDA 베이스 이미지를 쓰고, 나머지는 slim 이미지를 쓴다 |

### 7.2 컨테이너 이미지

| 서비스 | 베이스 |
|---|---|
| `db` | `postgres:16` 위에 `pg_bigm` 빌드 (`Dockerfile.db`) |
| `backend`, `collector` | `python:3.11-slim` |
| `translator` | `nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04` + PyTorch 2.6+cu124 |
| `frontend` (개발) | `node:20-slim` + Vite 개발 서버 |
| `frontend` (운영) | 정적 빌드 → `proxy`가 서빙 |

> ⚠️ **CUDA 12.1 고정.** 13.x는 Pascal 지원이 삭제돼 GPU 8장이 전부 무용지물이 된다.
> 베이스 이미지 태그를 올리지 말 것.

### 7.3 번역 큐 — DB 테이블 폴링

**메시지 브로커를 두지 않는다.** Redis/RabbitMQ 컨테이너를 추가할 만한 규모가 아니다
(배치당 320건, 하루 2회). `translation_jobs` 테이블을 `SELECT … FOR UPDATE SKIP LOCKED`로
집어가는 방식이면 워커 4개 경합이 안전하게 처리된다.

```sql
SELECT id FROM translation_jobs
 WHERE status = 'pending'
 ORDER BY created_at
 LIMIT 8
 FOR UPDATE SKIP LOCKED;
```

| ID | 요구사항 |
|---|---|
| A-3 | 번역 큐는 `translation_jobs` 테이블 + `FOR UPDATE SKIP LOCKED` 폴링으로 구현한다 |
| A-4 | 폴링 간격 2초, 큐가 비면 워커는 종료한다 (§4.2) |

### 7.4 리버스 프록시 — Caddy 도입

| 경로 | 대상 |
|---|---|
| `/api/*` | `backend:8000` |
| `/*` | 프론트엔드 정적 빌드 (운영) 또는 `frontend:3000` (개발) |

**왜 Caddy인가** — 설정이 짧고, 단일 오리진으로 묶어 CORS 설정 자체를 없앤다.
Nginx 대비 설정 파일이 10분의 1이다. TLS는 폐쇄망이라 내부 인증서 또는 평문.

### 7.5 마이그레이션 · 백업 · 로깅

| 항목 | 결정 |
|---|---|
| 마이그레이션 | **Alembic** (SQLAlchemy와 같은 계열) |
| 백업 | `pg_dump` 일 1회 → `backups/` (7일 보관). `db_data/` 볼륨 스냅샷은 따로 하지 않는다 |
| 로깅 | 표준출력 JSON 구조화 로그 → Docker 로그 드라이버. 별도 수집 스택 없음 |
| 배치 모니터링 | `batch_runs` 테이블에 소스별 성공/실패 건수 기록 (PRD-03 FR-26, PRD-01 FR-4) |

### 7.6 Compose 서비스 목록 (최종)

```
proxy       Caddy            80
frontend    Vite / 정적      3000 (개발만)
backend     FastAPI          8000
db          PG16 + pg_bigm   5432
collector   APScheduler      —      (상시, 09:00/21:00 트리거)
translator  PyTorch ×4       —      (배치 시각에만 기동, GPU 2장씩)
```

## 8. 데이터베이스 스키마 (개요)

| 테이블 | 용도 | 출처 |
|---|---|---|
| `contents` | 뉴스·논문 통합. `sections`는 JSONB, `searchKo`/`searchEn`은 생성 컬럼 | PRD-03 §6, PRD-05 §10.1 |
| `translation_jobs` | 번역 큐 | §7.3 |
| `batch_runs` | 배치 실행 이력·소스별 성공/실패 | PRD-03 FR-26 |
| `sources` | RSS 매체·키워드 설정 (관리자 변경 대상) | PRD-03 FR-37 |
| `users` | 회원·관리자 | PRD-01 §6 |
| `user_keywords` | 구독 키워드 (회원당 20개) | PRD-01 FR-15 |
| `refresh_tokens` | 세션 무효화 | PRD-01 FR-14 |
| `search_logs` | 질의어·시각·결과 건수. **회원 ID 미연결, 30일 보관** | PRD-02 §7 |

인덱스: `contents.searchKo` GIN(`pg_bigm`), `contents.searchEn` GIN(`tsvector`),
`contents(type, collected_at DESC)`, `contents.matched_keywords` GIN.

## 9. API 계약 (2026-09-23 확정)

화면이 5종이지만 **목록 계열은 엔드포인트 하나로 통일한다.** 메인·검색·카테고리 목록·
내 피드는 전부 "조건이 다른 목록 조회"이고, 응답 스키마가 같아야 프론트 컴포넌트를
재사용할 수 있다 (PRD-06 §7, §9.5).

| Method | Path | 설명 | 인증 |
|---|---|---|---|
| GET | `/api/contents` | **목록 통합** — 검색·카테고리·필터·정렬·페이지 | 불필요 |
| GET | `/api/main` | 메인 전용 번들 — 뉴스 9건 + 논문 6건을 1회 왕복으로 | 불필요 |
| GET | `/api/papers/{id}` | 논문 상세 — 3섹션 원문/번역 | 불필요 |
| GET | `/api/me/feed` | 구독 키워드 피드 — 내부적으로 `/api/contents`와 같은 질의 | 회원 |

`/api/contents` 파라미터:

| 파라미터 | 값 | 기본 |
|---|---|---|
| `q` | 검색어. 없으면 단순 목록 | — |
| `type` | `news` \| `paper` | 전체 |
| `category` | `international` \| `domestic` \| `paper` | 전체 |
| `kw` | `matchedKeywords` 다중(OR), 쉼표 구분 | — |
| `sort` | `relevance` \| `recent` | `q` 있으면 relevance, 없으면 recent |
| `page` / `size` | 페이지 번호 / 건수 | 1 / 20 |

응답: `{ items: [...], total, page, size, appliedScope }`
`appliedScope`는 검색 범위 표기용이다 (PRD-05 FR-17, PRD-06 FR-10).

인증 API는 PRD-01 §7, 관리자 API도 같은 표에 있다.

**공통 규약** — 모든 목록 응답의 `items[]`는 PRD-04 §7의 카드 필드를 포함하고,
`titleDisplay`/`summaryDisplay`는 **서버가 계산해서 내려준다**(PRD-03 FR-30~32).
프론트에서 폴백 분기를 하지 않는다.

## 10. 미결 사항

**없음.** 단 하나의 검증 게이트만 남았다 — **PRD-03 FR-42 번역 모델 벤치마크**(§4.1).
