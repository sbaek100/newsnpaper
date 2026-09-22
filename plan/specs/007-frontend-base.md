# SPEC-007: 프론트엔드 기반 (라우팅 · 토큰 · 공통 컴포넌트)

| 항목 | 값 |
|---|---|
| 근거 | roadmap.md 단계 6, design-system.md, architecture.md §6 |
| 목적 | 화면을 만들기 전에 **토큰·라우팅·공통 컴포넌트**를 갖춘다 |
| 선행 조건 | SPEC-006 (API가 있어야 카드에 실데이터를 붙일 수 있다) |
| 후행 | SPEC-008 메인·논문상세, SPEC-009 목록·검색 |

## 1. 범위

| 만든다 | 만들지 않는다 |
|---|---|
| `react-router-dom` 라우팅 5경로 | 실제 화면 (→ SPEC-008·009) |
| `tokens.css` — design-system.md 전량 이식 | 3D Hero (→ SPEC-008) |
| Pretendard 서브셋 + 로컬 배치 | |
| Placeholder SVG 6장 | |
| 공통 컴포넌트 (카드·배지·필터바·페이지네이션·상태화면) | |
| API 클라이언트 | |

## 2. 라우팅 (architecture.md §6)

| 경로 | 화면 | 담당 명세 |
|---|---|---|
| `/` | 메인 | SPEC-008 |
| `/papers/:id` | 논문 상세 | SPEC-008 |
| `/search` | 검색 결과 | SPEC-009 |
| `/news/international`, `/news/domestic`, `/papers` | 카테고리 목록 | SPEC-009 |
| `/feed` | 내 피드 (회원) | SPEC-009 |
| `/login`, `/signup` | 인증 | SPEC-009 |

| ID | 요구사항 |
|---|---|
| F-1 | `react-router-dom` 6을 도입한다 |
| F-2 | 위 경로에 **빈 플레이스홀더 페이지**를 붙여 라우팅이 동작함을 보인다 |
| F-3 | 필터·정렬·페이지 상태를 **URL 쿼리스트링에 반영**한다 (PRD-06 FR-6). 전역 상태로 들고 있지 마라 |
| F-4 | 404 경로를 둔다 |

## 3. 🔴 디자인 토큰 — `design-system.md`를 그대로 옮긴다

**값을 새로 만들지 마라.** `plan/design-system.md`에 전부 확정돼 있다.

| ID | 요구사항 |
|---|---|
| F-5 | `src/styles/tokens.css`에 §2(컬러)·§3.2(타이포)·§4.1(스페이싱)·§4.2(브레이크포인트)·§5(컴포넌트)를 **CSS 변수로** 선언한다 |
| F-6 | **색상값을 컴포넌트에 직접 쓰지 마라.** 항상 `var(--…)` (design-system §2.4 — 다크모드 대비) |
| F-7 | 다크 모드는 **구현하지 않는다.** 단 `:root[data-theme="dark"]` 블록만 추가하면 되게 구조를 남긴다 |
| F-8 | `--text-disabled`(`#8B95A1`)는 **정보 전달에 쓰지 마라.** 비활성·placeholder 전용 (§2.2) |
| F-9 | 카테고리 태그(국제/국내)는 **색으로 구분하지 않는다.** `--bg-subtle` 면 + `--text-secondary` 글자 (§2.3) |

### 3.1 폰트 (design-system §3.1)

| ID | 요구사항 |
|---|---|
| F-10 | Pretendard **로컬 서브셋**을 `public/fonts/`에 둔다. **CDN을 쓰지 마라** — 온프레미스에서 단일 실패점이 된다 |
| F-11 | 서브셋: KS X 1001 한글 2350자 + Latin + 숫자/기호, woff2, weight 400/500/600/700/800 |
| F-12 | `font-display: swap`, `@font-face`에 `unicode-range` 분리 |
| F-13 | **세리프를 쓰지 마라.** 전면 산세리프 단일 체계 (§3.1, C-8 해소) |

### 3.2 자산 (design-system §8)

| ID | 요구사항 |
|---|---|
| F-14 | Placeholder SVG **6장**을 직접 제작해 `public/placeholders/01~06.svg`에 둔다. 추상 노드·격자 패턴, 무채색 + `--point` 소량 |
| F-15 | **뉴스 카드 전용이다.** 논문 카드는 placeholder를 쓰지 않는다 (PRD-04 §4.2) |
| F-16 | 선택은 기사 `id` 해시 `% 6` — 리렌더마다 바뀌면 안 된다 |
| F-17 | placeholder는 장식이므로 `alt=""` + `aria-hidden` (design-system §9) |
| F-18 | 아이콘은 `lucide-react`. 16/20/24px, `stroke-width: 1.75`, `currentColor` (§5.1) |
| F-19 | 외부 스톡 이미지를 쓰지 마라 |

## 4. 공통 컴포넌트

### 4.1 카드 (PRD-04 §4.1·§4.2)

| ID | 요구사항 |
|---|---|
| F-20 | `NewsCard`와 `PaperCard`를 **별도 컴포넌트**로 만든다 (레이아웃이 다르다) |
| F-21 | **카드 루트가 `<a>`다.** 카드 전체가 하나의 링크 — 별도 "원문 이동 버튼"을 두지 마라 (C-4 해소) |
| F-22 | 뉴스 카드 → 외부 원문 (새 탭, `rel="noopener noreferrer"`) (PRD-04 FR-17) |
| F-23 | 논문 카드 → `/papers/:id` (사이트 내) (FR-17a) |
| F-24 | **논문 카드에 썸네일 슬롯을 두지 마라** (§4.2) |
| F-25 | 논문 카드는 좌측 `4px solid var(--paper)` 바 |
| F-26 | 논문 카드에 전문 확보 상태 배지 — "전문 분석" / "초록만" (FR-20) |
| F-27 | 유형 배지(뉴스/논문)는 **색 + 텍스트 라벨 병행** (design-system §9) |
| F-28 | 요약은 3줄 클램프. 요약이 없으면 제목 영역을 넓혀 빈 줄이 안 보이게 (PRD-03 FR-54) |
| F-29 | `titleDisplay`·`summaryDisplay`만 쓴다. **폴백 분기를 프론트에서 하지 마라** (PRD-03 FR-32) |

### 4.2 나머지

| ID | 요구사항 |
|---|---|
| F-30 | `FilterBar` — 타입 필터(뉴스/논문) + 키워드 칩(보안/해킹/사이버/AI) + 정렬 (PRD-06 §9.3) |
| F-31 | `Pagination` — **페이지 번호 방식**. 무한 스크롤을 쓰지 마라 (PRD-06 §9.1). 20건/페이지 |
| F-32 | 상태 화면 3종 — 로딩(**스켈레톤**, 스피너 금지) / 결과 없음 / 오류 (design-system §7) |
| F-33 | 빈 상태에 **일러스트를 쓰지 마라.** 텍스트만 (design-system §7) |
| F-34 | `Badge`, `Tag`, `Button`, `Input` 기본 컴포넌트 |
| F-35 | GNB — 로고(워드마크 `secubrief`), 카테고리 3종, 검색창, 계정 영역 (PRD-04 FR-1) |

## 5. API 클라이언트

| ID | 요구사항 |
|---|---|
| F-36 | `fetch` 래퍼 하나. 상대 경로 `/api/*`를 쓴다 (Caddy가 단일 오리진) |
| F-37 | 401이면 `/api/auth/refresh`를 1회 시도하고, 실패하면 로그인으로 보낸다 |
| F-38 | **액세스 토큰을 `localStorage`에 두지 마라.** 메모리에 두고, 리프레시는 httpOnly 쿠키가 처리한다 (PRD-01 FR-13) |

## 6. 🔴 하드 제약

| 제약 | 내용 |
|---|---|
| 토큰 | `design-system.md`의 값을 **그대로** 옮긴다. 임의로 바꾸지 마라 |
| 폰트 | CDN 금지, 로컬 서브셋 (F-10) |
| 다크모드 | 구현하지 마라 (F-7) |
| 무한 스크롤 | 쓰지 마라 (F-31) |
| Masonry | 쓰지 마라. 균일 CSS Grid (design-system §4.3) |
| 화면 | 이 명세에서 **실제 화면을 만들지 마라.** 플레이스홀더까지다 |
| 기존 파일 | `frontend/package.json`·`vite.config.js`는 있다. 의존성은 **추가**하되 기존 설정을 지우지 마라 |

## 7. 검증 방법

- [ ] `npm run dev` 후 6개 경로가 전부 열린다 (플레이스홀더라도)
- [ ] 없는 경로가 404 화면으로 간다
- [ ] `tokens.css`의 값이 `design-system.md`와 **전부 일치한다**
- [ ] 컴포넌트 소스에 하드코딩된 hex 색상이 **없다** (`grep -rE "#[0-9a-fA-F]{6}" src/ --include=*.jsx` 가 비어 있음)
- [ ] 폰트가 `public/fonts/`에서 로드된다. 네트워크 탭에 외부 도메인이 **없다**
- [ ] 뉴스 카드는 새 탭 외부 링크, 논문 카드는 `/papers/:id`로 간다
- [ ] 논문 카드에 이미지·placeholder가 **없다**
- [ ] 같은 기사를 여러 번 리렌더해도 placeholder가 **안 바뀐다**
- [ ] 필터를 걸면 URL이 바뀌고, 그 URL을 새 탭에 넣으면 같은 상태가 재현된다
- [ ] 모든 상호작용 요소에 포커스 링이 보인다
- [ ] 375px 폭에서 가로 스크롤이 없다

## 8. 보고할 것

```
CHANGED: <파일>
SUMMARY: <3줄 이내>
VERIFY:  <§7 각 항목>
TOKENS:  <design-system.md와 대조 결과 — 어긋난 값이 있으면 전부>
CONCERNS: <없으면 none>
```
