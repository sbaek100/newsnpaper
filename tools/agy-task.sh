#!/usr/bin/env bash
# agy-task.sh — Claude가 쓴 작업 명세를 Antigravity(agy)에 넘겨 구현시킨다.
#
#   tools/agy-task.sh plan/specs/001-scaffold.md
#   tools/agy-task.sh - <<<"프롬프트를 stdin으로"
#   tools/agy-task.sh plan/specs/002.md --model gemini-3.1-pro-high --dir frontend
#
# 옵션:
#   --model M   agy 모델 (기본: $AGY_MODEL 또는 gemini-3.1-pro-high)
#   --dir D     워크스페이스에 추가할 디렉토리 (반복 가능)
#   --plan      구현하지 않고 계획만 출력 (agy --mode plan)
#   --timeout T agy print 타임아웃 (기본 30m)
#
# 로그는 plan/agy-log/ 에 남는다.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL="${AGY_MODEL:-gemini-3.1-pro-high}"
MODE="accept-edits"
TIMEOUT="30m"
DIRS=()
SPEC=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)   MODEL="$2"; shift 2 ;;
    --dir)     DIRS+=(--add-dir "$2"); shift 2 ;;
    --plan)    MODE="plan"; shift ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -)         SPEC="-"; shift ;;
    -*)        echo "알 수 없는 옵션: $1" >&2; exit 2 ;;
    *)         SPEC="$1"; shift ;;
  esac
done

if [[ -z "$SPEC" ]]; then
  echo "사용법: tools/agy-task.sh <명세파일|-> [--model M] [--dir D] [--plan]" >&2
  exit 2
fi

if [[ "$SPEC" == "-" ]]; then
  PROMPT="$(cat)"
  SLUG="stdin"
else
  [[ -f "$SPEC" ]] || { echo "명세 파일 없음: $SPEC" >&2; exit 2; }
  PROMPT="$(cat "$SPEC")"
  SLUG="$(basename "$SPEC" .md)"
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="plan/agy-log/${STAMP}-${SLUG}.md"
mkdir -p plan/agy-log

# 모든 작업에 공통으로 붙는 머리말. 서버 하드 제약은 agy가 전역 CLAUDE.md를
# 읽지 않으므로 여기서 매번 주입한다.
PREAMBLE=$(cat <<'PRE'
너는 이 저장소의 구현 담당이다. 아래 작업 명세대로 코드를 작성/수정하라.

지켜야 할 제약:
- 저장소 루트의 CLAUDE.md와 plan/ 아래 PRD를 먼저 읽고 그 결정을 따른다.
- 명세에 없는 기능을 임의로 추가하지 않는다. 범위를 벗어나면 작업을 멈추고 이유를 보고한다.
- GPU 코드를 다룰 경우: 이 서버는 NVIDIA TITAN Xp x8, Pascal sm_61이다.
  bf16 사용 금지(에뮬레이션, fp32의 절반 속도). FlashAttention 사용 불가(sm_61 커널 없음).
  CUDA 12.1 / cuDNN 9.10.2 고정, 상위 버전 금지. GPU당 VRAM 12GB 독립 풀, NVLink 없음.
  CUDA 컴파일은 -arch=sm_61.
- 시크릿을 하드코딩하지 않는다. 환경변수로 뺀다.
- 작업이 끝나면 마지막에 다음 형식으로 요약하라:
    CHANGED: <바꾼 파일 경로를 한 줄에 하나씩>
    SUMMARY: <무엇을 왜 그렇게 했는지 3줄 이내>
    CONCERNS: <명세와 어긋나거나 확신이 없는 지점. 없으면 none>

--- 작업 명세 ---
PRE
)

{
  echo "# agy 실행 로그"
  echo
  echo "| 항목 | 값 |"
  echo "|---|---|"
  echo "| 시각 | $(date -Iseconds) |"
  echo "| 명세 | \`$SPEC\` |"
  echo "| 모델 | \`$MODEL\` |"
  echo "| 모드 | \`$MODE\` |"
  echo
  echo '## 프롬프트'
  echo
  echo '```'
  echo "$PROMPT"
  echo '```'
  echo
  echo '## 출력'
  echo
  echo '```'
} > "$LOG"

# agy의 --print 는 stdin을 읽지 않고 플래그에 붙은 값을 프롬프트로 쓴다.
FULL_PROMPT="${PREAMBLE}
${PROMPT}"

set +e
agy --print="$FULL_PROMPT" \
    --model "$MODEL" \
    --mode "$MODE" \
    --print-timeout "$TIMEOUT" \
    "${DIRS[@]}" \
  2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
set -e

{
  echo '```'
  echo
  echo "exit code: $RC"
} >> "$LOG"

echo
echo "--- 로그: $LOG (exit $RC) ---"
exit "$RC"
