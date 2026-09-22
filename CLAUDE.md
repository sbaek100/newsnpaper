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

## 🔴 agy 통제 규칙 (2026-09-23 실패 후 추가)

### 1. agy는 오래 걸리는 작업을 스스로 죽인다

agy는 장시간 작업을 **자기 내부 백그라운드 태스크로 띄운 뒤 몇 초 기다리다
세션을 종료하면서 자식 프로세스를 같이 죽인다.** 그러고도 **exit 0을 반환한다.**
`--timeout 240m`을 줘도 막지 못한다 — 그건 agy CLI 호출의 타임아웃일 뿐이다.

실제 사례: SPEC-001 벤치마크가 3분 만에 종료, 15GB 중 1GB만 받고 중단.
로그에 `terminating 1 background task(s) on exit`.

**따라서 일을 이렇게 나눈다:**

| 일 | 담당 |
|---|---|
| 코드 작성·수정 | **agy** (역할 분리 유지) |
| 짧은 검증·빌드·테스트 | agy |
| **장시간 실행** (모델 다운로드, 학습, 벤치마크, 대용량 수집) | **Claude가 `setsid`로 분리 실행** |

코드의 저자는 여전히 Antigravity다. 실행·검증은 원래 Claude의 역할이므로
역할 분리는 깨지지 않는다. 명세에 "실행까지 하라"고 적혀 있어도,
수 분을 넘길 작업이면 **코드 생성만 위임하고 실행은 Claude가 한다.**

장시간 실행은 이렇게:
```bash
nohup setsid env <ENV> <cmd> > <로그> 2>&1 < /dev/null &
```

### 2. agy의 자기 보고를 믿지 않는다

agy는 일을 하지 않고도 "완료했습니다"라고 보고한다.
보고 대신 **파일시스템과 git을 근거로만** 판단한다.

```bash
tools/agy-verify.sh [확인할 경로...]
```

이 스크립트가 검사하는 것 — git 변경 유무, 로그의 조기 종료·권한 거부 흔적,
산출물 실제 존재와 크기, Pascal 금지 패턴, 시크릿 유출.
**exit 1이면 agy 보고와 무관하게 실패로 간주한다.**

### 3. 래퍼가 조기 종료를 잡는다

`tools/agy-task.sh`는 실행 후 로그를 검사해 다음을 발견하면 **exit 90**을 낸다:
- `terminating N background task(s) on exit`
- `no output produced` / `auto-denied` (권한 거부)
- 보고 형식(`CHANGED:`)이 없음

**exit 90을 exit 0처럼 취급하지 마라.**

### 4. 위임 후 반드시 할 것

1. `tools/agy-verify.sh <기대 산출물 경로>` 실행
2. `git diff`로 실제 변경 내용을 읽는다 — 요약만 보지 마라
3. 해당 명세의 "검증 방법" 체크리스트를 **직접** 돌린다
4. 하드 제약 위반을 `grep`으로 확인한다

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
