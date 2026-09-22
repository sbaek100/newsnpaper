# 개발 로드맵

| 항목 | 값 |
|---|---|
| 상태 | **Confirmed** (2026-09-23) |
| 최종 수정 | 2026-09-23 |

> 모든 구현은 Antigravity(`agy`)가 수행한다. Claude는 명세를 쓰고 결과를 검증한다
> (`CLAUDE.md` 역할 분리). 각 단계는 `plan/specs/NNN-*.md` 명세로 위임한다.

---

## 단계 0 — 기반 (선행 필수)

| # | 작업 | 산출물 | 근거 |
|---|---|---|---|
| 0.1 | `git init` + `.gitignore` | 저장소 | PRD-02 §4. **검증(diff 리뷰)이 성립하려면 필수** |
| 0.2 | `docker-compose.yml` 골격 6서비스 | Compose 파일 | architecture.md §7.6 |
| 0.3 | `Dockerfile.db` — PG16 + `pg_bigm` | 커스텀 이미지 | architecture.md §2.1 |
| 0.4 | `secrets/` + `.env.example` | 시크릿 골격 | PRD-02 §3 |
| 0.5 | `shared/` 패키지 골격 (설정·DB 세션) | Python 패키지 | architecture.md A-1 |

## 단계 1 — 🔴 번역 벤치마크 (게이트)

| # | 작업 | 통과 기준 |
|---|---|---|
| 1.1 | Qwen2.5-7B-Instruct fp16을 GPU 2장에 로드 | OOM 없이 로드, `bf16`·FlashAttention 미사용 |
| 1.2 | 제목 80콜 / 논문 섹션 80콜 실소요 측정 | **워커당 80콜이 12시간 이내** |
| 1.3 | 한국어 번역 품질 샘플 검토 (20건) | 보안 용어가 깨지지 않음 |

> ⚠️ **미달 시 Qwen2.5-3B-Instruct fp16 × GPU 1장 × 8워커로 전환하고
> PRD-03 §8.1과 architecture.md §4를 고친 뒤 진행한다.**
> 이 단계 전에 다른 구현을 진행해도 되지만, `translator`는 여기 결과를 기다린다.

## 단계 2 — 데이터 계층

| # | 작업 | 근거 |
|---|---|---|
| 2.1 | SQLAlchemy 모델 8테이블 | architecture.md §8 |
| 2.2 | `IMMUTABLE` 헬퍼 + `searchKo`/`searchEn` 생성 컬럼 | PRD-05 §10.1 FR-23 |
| 2.3 | GIN 인덱스 (`pg_bigm` / `tsvector`) | PRD-05 FR-19·FR-20 |
| 2.4 | Alembic 초기 마이그레이션 | architecture.md §7.5 |

## 단계 3 — 수집 파이프라인

| # | 작업 | 근거 |
|---|---|---|
| 3.1 | arXiv + Semantic Scholar 수집기 | PRD-03 FR-21·FR-35 |
| 3.2 | RSS 7개 매체 + GDELT + Naver 수집기 | PRD-03 FR-22·FR-36 |
| 3.3 | dedup (URL 정규화 + DOI/arXiv ID) | PRD-03 FR-24, §4.2 |
| 3.4 | PDF 다운로드 → 텍스트 추출 → 섹션 휴리스틱 → PDF 삭제 | PRD-03 FR-14·FR-51 |
| 3.5 | `matchedKeywords[]` 기록, 수집 상한 적용 | PRD-03 FR-33·FR-27 |
| 3.6 | APScheduler 09:00/21:00, `batch_runs` 기록 | PRD-03 FR-38·FR-26 |

## 단계 4 — 번역 워커

| # | 작업 | 근거 |
|---|---|---|
| 4.1 | `translation_jobs` 큐 + `FOR UPDATE SKIP LOCKED` | architecture.md A-3 |
| 4.2 | 워커 4개 기동/종료 스크립트, GPU 짝 할당 | architecture.md §4 |
| 4.3 | 용어집 주입 프롬프트 | PRD-03 FR-48~50 |
| 4.4 | 재시도 3회 + 지수 백오프 | PRD-03 FR-45·FR-46 |
| 4.5 | `titleDisplay`/`summaryDisplay` 파생 로직 | PRD-03 FR-30~32 |

## 단계 5 — 백엔드 API

| # | 작업 | 근거 |
|---|---|---|
| 5.1 | 목록·검색 조회 API (공통 응답 스키마) | PRD-06 §7 |
| 5.2 | 검색 질의 — 한/영 분기, 랭킹 가중치 | PRD-05 §6.1·§10.3 |
| 5.3 | 인증 (Argon2id, JWT 30분 + 리프레시 14일) | PRD-01 §5, PRD-02 §5 |
| 5.4 | 구독 키워드 CRUD + `/api/me/feed` | PRD-01 FR-6·FR-7 |
| 5.5 | 관리자 API (소스 관리, 배치 조회) | PRD-01 FR-3·FR-4 |
| 5.6 | 로그 마스킹, 검색어 로그 30일 삭제 배치 | PRD-02 §6, FR-20 |

## 단계 6 — 프론트엔드 기반

| # | 작업 | 근거 |
|---|---|---|
| 6.1 | Vite + react-router-dom 라우팅 5경로 | architecture.md §6 |
| 6.2 | `tokens.css` — design-system.md 전량 이식 | design-system §1~5 |
| 6.3 | Pretendard 서브셋 생성 + 로컬 배치 | design-system §3.1 |
| 6.4 | Placeholder SVG 6장 제작 | design-system §8 |
| 6.5 | 공통 컴포넌트 — 카드(뉴스/논문), 배지, 필터 바, 페이지네이션, 상태 화면 | PRD-04 §4.1·4.2, design-system §7 |

## 단계 7 — 화면

| # | 화면 | 근거 |
|---|---|---|
| 7.1 | 메인 — GNB, 3D Hero, 뉴스/논문 섹션 | PRD-04 |
| 7.2 | 논문 상세 `/papers/:id` | PRD-04 §10 |
| 7.3 | 검색 결과 `/search` | PRD-06 §4.2 |
| 7.4 | 카테고리 목록 3종 | PRD-06 §4.3 |
| 7.5 | 로그인·가입·내 피드 `/feed` | PRD-01 §10, PRD-06 §9.5 |

## 단계 8 — 마무리

| # | 작업 |
|---|---|
| 8.1 | Caddy 프록시 + 운영 정적 빌드 |
| 8.2 | 접근성 점검 — 대비비, 포커스, `aria-*`, `prefers-reduced-motion` |
| 8.3 | 수용 기준 전수 확인 (각 PRD의 "수용 기준" 절) |
| 8.4 | `pg_dump` 일 1회 백업 |

---

## 의존 관계

```
0 기반
├─▶ 1 번역 벤치마크 ──────────┐
├─▶ 2 데이터 계층 ──┬─▶ 3 수집 ─┴─▶ 4 번역 워커 ─┐
│                   └─▶ 5 백엔드 API ◀───────────┘
└─▶ 6 프론트 기반 ──▶ 7 화면 ◀── 5
                              └─▶ 8 마무리
```

단계 1과 단계 2·6은 **병행 가능**하다. 단계 4는 1의 결과를 기다린다.

## 1차 범위에서 의도적으로 제외한 것

| 항목 | 이유 | 문서 |
|---|---|---|
| 뉴스 본문 수집·검색 | 저작권 검토 + 매체별 파서 유지보수 | PRD-05 §4.1 |
| 한국어 질의의 논문 전문 검색 | GPU 부하. 2차 과제로 기록 | PRD-05 §10.6 |
| 검색 자동완성 | 로그가 쌓인 뒤 인기어 기반으로 | PRD-05 §10.4 |
| 다크 모드 | 토큰은 CSS 변수로 남겨 둠 | design-system §2.4 |
| 소셜 로그인 · 이메일 인증 · 비밀번호 찾기 메일 | 메일 인프라 없음 | PRD-01 §9 |
| 알림(메일/인앱) | 구독 키워드 신규 항목 알림 | PRD-01 §3 |
| RAG / 자연어 질의응답 | | PRD-05 §2 |
