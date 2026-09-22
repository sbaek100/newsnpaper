# 기획 · 아키텍처 문서

'컴퓨터 및 정보 보안' 테마의 뉴스·논문 자동 수집 + AI 번역 큐레이션 서비스
**시큐브리프(secubrief)** 의 요구사항·아키텍처·디자인 문서 모음.

> **진행 상태 (2026-09-23)**
> 요구사항 정리가 **끝났다.** 충돌 13건 전부 해소, 남은 미결 0건.
> 유일한 게이트는 **번역 모델 벤치마크**(PRD-03 FR-42)이며 구현 단계 1에서 수행한다.
>
> 구현은 **Antigravity(`agy`)가 수행하고 Claude가 명세·검증을 맡는다** — `../CLAUDE.md` 참조.

## 구조

```
plan/
├── README.md          이 파일 — 문서 색인
├── TEMPLATE.md        PRD 작성 템플릿
├── CONFLICTS.md       요구사항 충돌 해소 기록 (13건 전부 해소)
├── architecture.md    서비스 구성, 스택, DB 스키마, GPU 제약
├── design-system.md   디자인 토큰 단일 진실 공급원
├── roadmap.md         단계별 개발 로드맵 (단계 0~8)
├── prd/               기능별 요구사항 정의서
├── specs/             Antigravity에 넘길 작업 명세 (구현 시 생성)
└── agy-log/           agy 실행 로그 (gitignore 대상)
```

## 문서 색인

| 번호 | 문서 | 주제 | 상태 |
|---|---|---|---|
| 01 | `prd/01-auth.md` | 인증 / 권한 / 키워드 구독 | ✅ Confirmed |
| 02 | `prd/02-secrets.md` | 시크릿 · 개인정보 관리 | ✅ Confirmed |
| 03 | `prd/03-ingest-translate.md` | 뉴스·논문 수집 및 AI 번역 | ✅ Confirmed |
| 04 | `prd/04-main-page-ui.md` | 메인 페이지 + 논문 상세 페이지 | ✅ Confirmed |
| 05 | `prd/05-search.md` | 검색 (질의·색인·랭킹) | ✅ Confirmed |
| 06 | `prd/06-list-pages.md` | 검색 결과 · 카테고리 목록 페이지 | ✅ Confirmed |
| — | `architecture.md` | 시스템 아키텍처 | ✅ Confirmed |
| — | `design-system.md` | 디자인 시스템 | ✅ Confirmed |
| — | `roadmap.md` | 개발 로드맵 | ✅ Confirmed |

상태 범례: ⬜ 내용 대기 · 🟡 Draft · 🔵 Review · ✅ Confirmed

## 핵심 결정 요약

| 영역 | 결정 |
|---|---|
| 배포 | Docker Compose 온프레미스, 서비스 6종 (proxy/frontend/backend/db/collector/translator) |
| 스택 | Python 3.11 + FastAPI · PostgreSQL 16 + `pg_bigm` · React 18 + Vite 5 + react-router-dom |
| 수집 | 하루 2회(09:00/21:00), 배치당 뉴스 100 / 논문 30 |
| 소스 | arXiv(cs.CR) · Semantic Scholar · RSS 7매체 · GDELT · Naver 검색 API |
| 번역 | 온프레미스 Qwen2.5-7B-Instruct fp16, GPU 2장 × 4워커, 배치 시각에만 기동 |
| 검색 | 별도 검색엔진 없음. `pg_bigm`(한국어) + `tsvector`(영어) |
| 본문 검색 | 논문 PDF 전문을 **번역 없이 영어로만** 색인. 뉴스 본문은 미수집 |
| 화면 | 메인 / 논문 상세 / 검색 결과 / 카테고리 목록 3종 / 내 피드 |
| 회원 | 이메일+비밀번호, 관심 키워드 구독(저장분 필터, 20개 상한) |
| 디자인 | 화이트 기조, Pretendard 단일 산세리프, 다크 모드 1차 미지원 |

## 작성 규칙

- PRD 파일명은 `{2자리 번호}-{영문 슬러그}.md`
- 문서 상단 표의 `상태`를 갱신하고 이 README 색인도 함께 갱신
- **색상·크기 값은 `design-system.md`에만 적는다.** PRD에 중복하지 않는다
- 결정이 바뀌면 `CONFLICTS.md`에 왜 바뀌었는지 남긴다
