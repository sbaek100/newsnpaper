# mypage — 작업 규칙

## 역할 (2026-09-23 변경)

**Claude가 직접 개발한다.** 이전의 "코딩은 Antigravity" 규칙은 폐기한다.

| 단계 | 담당 |
|---|---|
| 요구사항·설계 | Claude |
| **코드 작성·수정** | **Claude** |
| 실행·검증 | Claude |

`plan/specs/`의 명세는 **구현 체크리스트로만** 쓴다. 위임용이 아니다.
새 작업마다 명세 문서를 새로 쓰지 않는다 — 바로 구현한다.

### 구현 착수 게이트

`plan/README.md`의 PRD가 `Confirmed`가 아니면 구현하지 않는다.
사용자가 명시적으로 지시한 경우는 예외.

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
