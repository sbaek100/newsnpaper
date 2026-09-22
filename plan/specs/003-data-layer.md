# SPEC-003: 데이터 계층 (모델 · 색인 · 마이그레이션)

| 항목 | 값 |
|---|---|
| 근거 | roadmap.md 단계 2, architecture.md §8, PRD-03 §6, PRD-05 §10.1 |
| 목적 | 8개 테이블과 **검색 색인**을 만든다. 애플리케이션 로직은 없다 |
| 선행 조건 | **SPEC-002 완료** (`db` 컨테이너가 `pg_bigm`과 함께 떠 있어야 한다) |
| 후행 | SPEC-004 수집, SPEC-006 API |

## 1. 범위

| 만든다 | 만들지 않는다 |
|---|---|
| SQLAlchemy 2.0 모델 8종 | 수집·번역·검색 **로직** |
| `pg_bigm` / `tsvector` GIN 인덱스 | API 엔드포인트 |
| `IMMUTABLE` 헬퍼 함수 + 생성 컬럼 | 인증 처리 |
| Alembic 초기 마이그레이션 | 시드 데이터(콘텐츠) |
| `sources` 초기 시드 (RSS 매체·키워드) | |

`shared/db.py`는 SPEC-002에서 엔진·세션만 만들었다. **모델은 여기서 추가한다.**

## 2. 테이블 (architecture.md §8)

### 2.1 `contents` — 뉴스·논문 통합

PRD-03 §6의 필드를 그대로 따른다. **뉴스·논문을 한 테이블에 둔다** — 목록·검색이
둘을 섞어 조회하므로(PRD-06 §9.2) 분리하면 UNION이 상시 필요해진다.

| 그룹 | 컬럼 |
|---|---|
| 공통 | `id`, `type`(`news`\|`paper`), `category`, `source_url`, `collected_at`, `language`, `title_original`, `title_ko`, `translation_status`, `matched_keywords`(ARRAY), `thumbnail_url` |
| 뉴스 | `summary_original`, `summary_ko` |
| 논문 | `authors`(ARRAY), `venue`, `published_at`, `doi`, `arxiv_id`, `pdf_url`, `sections`(JSONB), `section_extract_status`, `full_text_original`, `full_text_status` |
| 색인 | `search_ko`, `search_en` (생성 컬럼, §3) |

| ID | 요구사항 |
|---|---|
| D-1 | `source_url`에 UNIQUE 제약 — dedup의 1차 키 (PRD-03 FR-24) |
| D-2 | `doi`, `arxiv_id`에 부분 UNIQUE 인덱스(NULL 허용) — 논문 dedup 우선 키 (PRD-03 §4.2) |
| D-3 | `translation_status` = `pending`\|`done`\|`failed`\|`skipped` (PRD-03 FR-9·FR-10) |
| D-4 | `section_extract_status` = `full`\|`abstract_only`\|`failed` (PRD-03 FR-15) |
| D-5 | `full_text_status` = `indexed`\|`no_pdf`\|`extract_failed` (PRD-03 FR-29b) |
| D-6 | `sections`는 JSONB — `[{"name":..., "textOriginal":..., "textKo":...}]` (PRD-05 §10.1) |
| D-7 | `(type, collected_at DESC)` 복합 인덱스 — 목록 기본 정렬 |
| D-8 | `matched_keywords`에 GIN 인덱스 (PRD-06 §9.3 필터) |
| D-9 | `full_text_original`은 저장 전 **200,000자로 자른다** (PRD-03 FR-52). DB 제약이 아니라 애플리케이션 책임이지만, 컬럼 주석으로 남겨라 |

> **`title_display` / `summary_display`는 컬럼으로 만들지 않는다.**
> API 응답 시 계산해서 내려준다 (PRD-03 FR-30~32). DB에 중복 저장할 이유가 없다.

### 2.2 나머지 7종

| 테이블 | 핵심 컬럼 | 근거 |
|---|---|---|
| `translation_jobs` | `id`, `content_id`, `field`(어느 필드를 번역하는지), `status`, `attempts`, `last_error`, `created_at`, `started_at`, `finished_at` | architecture.md §7.3 |
| `batch_runs` | `id`, `started_at`, `finished_at`, `status`, `stats`(JSONB — 소스별 성공/실패) | PRD-03 FR-26 |
| `sources` | `id`, `kind`(`rss`\|`api`\|`arxiv`), `name`, `url`, `category`, `enabled`, `created_at` | PRD-03 FR-37 |
| `users` | `id`, `email`(UNIQUE), `password_hash`, `role`, `must_change_password`, `created_at` | PRD-01 §6 |
| `user_keywords` | `id`, `user_id`, `keyword`, `created_at` | PRD-01 FR-15 (20개 상한은 애플리케이션 검증) |
| `refresh_tokens` | `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at` | PRD-01 FR-14 |
| `search_logs` | `id`, `query`, `result_count`, `created_at` | PRD-02 FR-19 — **`user_id` 컬럼을 두지 마라** |

| ID | 요구사항 |
|---|---|
| D-10 | `translation_jobs.status` = `pending`\|`running`\|`done`\|`failed`. `(status, created_at)` 인덱스 — 큐 폴링용 |
| D-11 | `user_keywords`에 `(user_id, keyword)` UNIQUE — 같은 키워드 중복 등록 방지 |
| D-12 | `users`, `user_keywords`, `refresh_tokens`는 `ON DELETE CASCADE`로 묶어 탈퇴 시 함께 지워진다 (PRD-01 FR-16) |
| D-13 | **`search_logs`에 회원 식별자를 두지 마라** (PRD-02 FR-19). FK도 두지 마라 |

## 3. 🔴 검색 색인 — 이 명세의 핵심

PRD-05 §6.1: 한국어는 `pg_bigm` 2그램, 영어는 PostgreSQL FTS.

### 3.1 생성 컬럼과 IMMUTABLE 문제

```sql
search_ko TEXT GENERATED ALWAYS AS ( ... ) STORED
```

PostgreSQL 생성 컬럼은 **IMMUTABLE 식만** 허용한다. `sections` JSONB에서
텍스트를 뽑는 서브쿼리는 그대로는 쓸 수 없다. **`IMMUTABLE`로 마킹한 헬퍼 함수로 감싸야 한다.**

| ID | 요구사항 |
|---|---|
| D-14 | `sections` JSONB에서 번역문(`textKo`)을 이어붙이는 `IMMUTABLE` 함수를 만든다 |
| D-15 | 원문(`textOriginal`)용 함수도 같이 만든다 |
| D-16 | `search_ko` = `title_ko` + `summary_ko` + 섹션 번역문 (생성 컬럼, STORED) |
| D-17 | `search_en` = `title_original` + `summary_original` + 섹션 원문 + `full_text_original` (생성 컬럼, STORED) |
| D-18 | 함수가 NULL 입력에 안전해야 한다 (`coalesce` 처리). 하나라도 NULL이면 전체가 NULL이 되면 안 된다 |

> 생성 컬럼이 끝내 불가능하면 **트리거로 대체**하고 그 사실을 보고하라 (PRD-05 FR-22).
> 임의로 애플리케이션 코드에서 채우는 방식으로 바꾸지 마라 — 본문과 색인이 어긋난다.

### 3.2 인덱스

| ID | 요구사항 |
|---|---|
| D-19 | `search_ko`에 `pg_bigm` GIN 인덱스 (`gin_bigm_ops`) — PRD-05 FR-19 |
| D-20 | `search_en`에 `to_tsvector('english', search_en)` 식 기반 GIN 인덱스 — PRD-05 FR-20 |
| D-21 | 마이그레이션에서 `CREATE EXTENSION IF NOT EXISTS pg_bigm;`을 먼저 실행한다 |

## 4. Alembic

| ID | 요구사항 |
|---|---|
| D-22 | `alembic/` 초기화, `shared/config.py`의 DB URL을 읽어 쓴다 |
| D-23 | 초기 리비전 하나에 8테이블 + 함수 + 인덱스를 전부 담는다 |
| D-24 | `downgrade()`도 구현한다 (함수·확장 포함) |
| D-25 | `alembic upgrade head` / `downgrade base`가 왕복으로 동작한다 |

## 5. `sources` 초기 시드

PRD-03 §7.2~7.3의 목록을 넣는다.

| kind | name | category |
|---|---|---|
| `rss` | BleepingComputer · The Hacker News · Krebs on Security · SecurityWeek · Dark Reading | international |
| `rss` | 보안뉴스 · 데일리시큐 | domestic |
| `api` | GDELT 2.0 DOC | international |
| `api` | Naver 검색(news) | domestic |
| `arxiv` | arXiv cs.CR / cs.AI / cs.LG | paper |

| ID | 요구사항 |
|---|---|
| D-26 | 시드는 **마이그레이션이 아니라 별도 스크립트**(`tools/seed-sources.py`)로 둔다. 재실행해도 중복되지 않는다(UPSERT) |
| D-27 | 각 RSS의 실제 피드 URL을 조사해 넣는다. 확인 못 한 항목은 `enabled=false`로 두고 보고하라 |

## 6. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| 모델만 | **수집·번역·검색 로직을 쓰지 마라.** 모델·마이그레이션·시드까지다 |
| 시크릿 | DB 비밀번호를 코드·마이그레이션에 쓰지 마라. `shared/config.py`를 거친다 |
| `search_logs` | 회원 식별자 컬럼을 두지 마라 (PRD-02 FR-19) |
| 기존 파일 | SPEC-002가 만든 `shared/config.py`·`db.py`를 **지우지 말고 확장**하라 |
| `benchmarks/` | 건드리지 마라 |

## 7. 검증 방법

- [ ] `alembic upgrade head` 성공
- [ ] `\dt` 로 8개 테이블이 보인다
- [ ] `\di` 로 `pg_bigm` GIN 인덱스와 `tsvector` GIN 인덱스가 보인다
- [ ] 더미 행 1개를 넣으면 `search_ko`·`search_en`이 **자동으로 채워진다**
- [ ] `sections`가 NULL인 행에서도 `search_ko`가 NULL이 아니다 (D-18)
- [ ] `SELECT * FROM contents WHERE search_ko LIKE '%랜섬웨어%'` 가 GIN 인덱스를 탄다 (`EXPLAIN` 확인)
- [ ] 조사 결합 테스트 — `search_ko`에 "랜섬웨어가 확산"이 든 행이 `'랜섬웨어'` 질의에 걸린다
- [ ] `python tools/seed-sources.py` 두 번 실행해도 행이 늘지 않는다
- [ ] `alembic downgrade base` 가 깨끗하게 되돌린다
- [ ] `search_logs`에 `user_id` 컬럼이 **없다**

## 8. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
VERIFY:  <§7 각 항목 통과/실패>
INDEX:   <EXPLAIN 결과 — GIN 인덱스를 실제로 타는지>
CONCERNS: <생성 컬럼을 트리거로 대체했다면 반드시 여기 적어라. 없으면 none>
```
