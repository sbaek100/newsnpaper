# SPEC-006: 백엔드 API

| 항목 | 값 |
|---|---|
| 근거 | roadmap.md 단계 5, architecture.md §9, PRD-01 §7, PRD-05, PRD-06 §7 |
| 목적 | 조회·검색·인증 API를 완성한다 |
| 선행 조건 | SPEC-003 (스키마), SPEC-004 (데이터가 있어야 검색 검증 가능) |
| 후행 | SPEC-007~009 프론트엔드 |

## 1. 엔드포인트 (architecture.md §9)

**목록 계열은 하나로 통일한다.** 메인·검색·카테고리 목록·내 피드가 전부
"조건이 다른 목록 조회"이고, 응답 스키마가 같아야 프론트가 컴포넌트를 재사용한다.

| Method | Path | 인증 |
|---|---|---|
| GET | `/api/contents` | 불필요 |
| GET | `/api/main` | 불필요 |
| GET | `/api/papers/{id}` | 불필요 |
| GET | `/api/health` | 불필요 |
| POST | `/api/auth/signup` · `/login` · `/refresh` · `/logout` · `/password` | 각각 |
| DELETE | `/api/auth/me` | 회원 |
| GET·PUT | `/api/me/keywords` | 회원 |
| GET | `/api/me/feed` | 회원 |
| GET·PUT | `/api/admin/sources` | 관리자 |
| GET | `/api/admin/batches` | 관리자 |
| POST | `/api/admin/translations/{id}/retry` | 관리자 |

### 1.1 `/api/contents` 파라미터

| 파라미터 | 값 | 기본 |
|---|---|---|
| `q` | 검색어. 없으면 단순 목록 | — |
| `type` | `news` \| `paper` | 전체 |
| `category` | `international` \| `domestic` \| `paper` | 전체 |
| `kw` | `matched_keywords` 다중(OR), 쉼표 구분 | — |
| `sort` | `relevance` \| `recent` | `q` 있으면 relevance, 없으면 recent |
| `page` / `size` | 1 / 20 | |

응답: `{ items: [...], total, page, size, appliedScope }`

| ID | 요구사항 |
|---|---|
| B-1 | `size` 상한을 100으로 막는다 (DoS 방지) |
| B-2 | `appliedScope`는 검색 범위 표기용 문자열이다 (PRD-05 FR-17, PRD-06 FR-10) |
| B-3 | `kw`와 `category`가 동시에 오면 **AND**로 적용한다 (PRD-06 §9.3) |
| B-4 | `/api/me/feed`는 회원의 구독 키워드를 `q`로 삼아 **같은 질의 경로**를 탄다 (PRD-01 §3.2). 별도 매칭 엔진을 만들지 마라 |

## 2. 🔴 응답 공통 규약

| ID | 요구사항 |
|---|---|
| B-5 | `items[]`의 `titleDisplay` = `title_ko ?? title_original` — **서버가 계산해 내려준다** (PRD-03 FR-30) |
| B-6 | `summaryDisplay` = `summary_ko ?? summary_original` (FR-31) |
| B-7 | 프론트가 폴백 분기를 하지 않게 **원본 필드를 그대로 노출하지 마라** (FR-32) |
| B-8 | 논문 카드 응답에 `thumbnailUrl`을 넣지 마라 — 논문은 썸네일을 쓰지 않는다 (PRD-04 §4.2) |
| B-9 | **`full_text_original`을 어떤 응답에도 넣지 마라** — 검색 색인 전용이다 (PRD-04 FR-29) |

## 3. 검색 (PRD-05)

| ID | 요구사항 |
|---|---|
| B-10 | 질의어에 한글이 있으면 `search_ko`를 `pg_bigm`으로, 영문이면 `search_en`을 `tsvector`로 매칭한다. 섞여 있으면 둘 다 (FR-5) |
| B-11 | **1글자 질의는 거부한다** — 2그램 특성상 노이즈가 심하다 (FR-21) |
| B-12 | 관련도 랭킹 — 제목 3.0 / 요약·초록 1.5 / 본문 1.0 / 최근 7일 가산 0.3. **가중치는 설정으로 조정 가능하게** (FR-24) |
| B-13 | 기본 정렬은 검색이면 `relevance`, 목록이면 `recent` (FR-25) |
| B-14 | `translation_status='failed'` 항목도 원문 기준으로 검색된다 (FR-13) |
| B-15 | 하이라이트용 매칭 위치를 응답에 포함한다 (PRD-05 FR-7, PRD-06 FR-11) |
| B-16 | 영어 질의가 `full_text_original`에서만 매칭됐으면 그 사실을 표시한다 (FR-18) |
| B-17 | 검색 실행 시 `search_logs`에 기록한다 — **회원 식별자를 남기지 마라** (PRD-02 FR-19) |

## 4. 인증 (PRD-01 §5, PRD-02 §5)

| ID | 요구사항 |
|---|---|
| B-18 | 비밀번호 해싱 **Argon2id** — `memory=64MiB, iterations=3, parallelism=4` (PRD-02 FR-9) |
| B-19 | 비밀번호 최소 10자, 동일 문자 4회 반복 금지 (FR-10) |
| B-20 | 액세스 토큰 30분, 리프레시 14일 (PRD-01 FR-12) |
| B-21 | 리프레시는 `httpOnly`·`Secure`·`SameSite=Lax` **쿠키로만**. 로컬 스토리지 금지 (FR-13) |
| B-22 | 로그아웃 시 `refresh_tokens.revoked_at`을 채워 무효화한다 (FR-14) |
| B-23 | JWT 서명 키는 `secrets/jwt_secret`에서 읽는다 (PRD-02 FR-11) |
| B-24 | 구독 키워드 **20개 상한**을 서버에서 강제한다 (FR-15) |
| B-25 | 탈퇴 시 회원·구독 키워드·리프레시 토큰을 즉시 삭제한다 (FR-16) |
| B-26 | 로그인 실패 **계정당 5회/10분** 제한 (PRD-02 FR-13) |
| B-27 | `must_change_password`가 `true`면 다른 API를 막고 비밀번호 변경만 허용한다 (FR-12) |
| B-28 | **권한 검사는 서버에서 강제한다.** 프론트 표시 제어에 의존하지 마라 (PRD-01 FR-5) |

## 5. 로깅 (PRD-02 §6)

| ID | 요구사항 |
|---|---|
| B-29 | `shared/logging.py`의 마스킹을 적용한다 — `password`, `token`, `authorization`, `cookie`, `secret`, `apiKey`, `clientSecret` (FR-15) |
| B-30 | 이메일은 `a***@example.com`으로 부분 마스킹 (FR-16) |
| B-31 | `search_logs` 30일 삭제 배치를 둔다 (FR-20). `collector` 스케줄러에 붙여도 된다 |

## 6. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| CORS | **CORS 설정을 넣지 마라.** Caddy가 단일 오리진으로 묶는다 (PRD-06/architecture.md §7.4, S-34) |
| 시크릿 | 환경변수가 아니라 `*_FILE` 경로로 읽는다 (PRD-02 FR-2·FR-3) |
| N+1 | 목록 조회에서 논문 `sections`를 행마다 따로 읽지 마라. 카드에는 섹션이 필요 없다 |
| 색인 | 검색은 반드시 **GIN 인덱스를 타야 한다**. `LIKE '%…%'` 풀스캔으로 떨어지면 실패다 |
| `full_text` | 응답에 넣지 마라 (B-9) |

## 7. 검증 방법

- [ ] `/api/health`가 DB 연결까지 확인한다
- [ ] `/api/contents?q=랜섬웨어` 가 번역문에서 매칭된다
- [ ] `/api/contents?q=ransomware` 가 원문·논문 전문에서 매칭된다
- [ ] "랜섬웨어**가**"로 검색해도 "랜섬웨어" 항목이 나온다 (조사 결합)
- [ ] `EXPLAIN`으로 검색 질의가 **GIN 인덱스를 탄다**
- [ ] 1글자 질의가 400으로 거부된다
- [ ] `?type=paper` 필터가 동작하고, `?kw=보안,AI`가 OR로 걸린다
- [ ] 국내 뉴스(`translation_status='skipped'`)의 `titleDisplay`가 원문 제목이다
- [ ] 어떤 응답에도 `fullTextOriginal`이 **없다**
- [ ] 논문 응답에 `thumbnailUrl`이 **없다**
- [ ] 일반 회원이 `/api/admin/*`를 부르면 **403**
- [ ] 로그아웃 후 이전 리프레시 쿠키로 재발급이 **안 된다**
- [ ] 구독 키워드 21개째가 거부된다
- [ ] 6회 로그인 실패 시 차단된다
- [ ] 로그에 비밀번호·토큰이 평문으로 없다
- [ ] `search_logs`에 회원 식별자가 없다

## 8. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
VERIFY:  <§7 각 항목>
INDEX:   <검색 질의의 EXPLAIN 결과 — GIN을 타는지>
CONCERNS: <없으면 none>
```
