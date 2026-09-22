# mypage — 작업 규칙

## 역할 분리 (2026-09-23 확정)

이 프로젝트는 **계획·검증은 Claude, 구현은 Antigravity**로 분리한다.

| 단계 | 담당 | 산출물 |
|---|---|---|
| 요구사항 정의 | Claude | `plan/prd/*.md` |
| 작업 명세 작성 | Claude | `plan/specs/NNN-*.md` |
| **코드 작성·수정** | **Antigravity (`agy`)** | `backend/`, `frontend/` 등 |
| 리뷰·검증 | Claude | 리뷰 코멘트, 재작업 명세 |

### Claude가 지켜야 할 것

1. **`backend/`, `frontend/`, `db_data/` 아래의 애플리케이션 코드를
   `Edit`/`Write`로 직접 작성하거나 수정하지 않는다.**
   구현이 필요하면 작업 명세를 쓰고 `antigravity-coder` 서브에이전트에 위임한다.
2. 예외 — 아래는 Claude가 직접 다뤄도 된다:
   - `plan/` 전체 (PRD, 명세, 로그)
   - `CLAUDE.md`, `.claude/`, `tools/` (이 워크플로 자체의 설정)
3. 검증 단계에서 버그를 찾으면 **직접 고치지 말고** 재작업 명세를 써서 다시 위임한다.
   단 한 줄짜리 오타여도 마찬가지다 — 코드의 단일 저자를 Antigravity로 유지한다.
4. 위임 전에 해당 기능의 PRD가 `Confirmed` 상태인지 확인한다 (아래 게이트).

### 구현 착수 게이트

`plan/README.md`의 PRD 색인에서 해당 문서가 **✅ Confirmed**가 아니면
구현을 위임하지 않는다. 사용자가 명시적으로 지시한 경우에만 예외.

## Antigravity 사용 시 주의

`agy`는 Google 계정 OAuth로 **외부 모델에 붙는다.** 따라서:

- **수집된 뉴스·논문 콘텐츠를 `agy`에 넣지 말 것.**
  PRD-03 FR-13이 "온프레미스 LLM으로 처리하며 외부 API로 콘텐츠를 전송하지 않는다"로
  확정돼 있다. `agy`는 소스코드 작성 용도로만 쓴다.
- `.env`, 시크릿, `db_data/`의 실제 데이터를 컨텍스트에 포함시키지 말 것 (PRD-02 연계).

## 서버 제약

GPU 관련 제약은 `~/.claude/CLAUDE.md`(전역)와 `plan/architecture.md` §3 참조.
요약: Pascal sm_61 — `bf16` 금지, FlashAttention 불가, CUDA 12.1 고정, GPU당 12GB 독립 풀.
이 제약은 작업 명세에 **매번 명시**해서 Antigravity에 전달한다 (`agy`는 이 파일을 읽지만
전역 CLAUDE.md는 읽지 않는다).
