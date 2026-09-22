#!/usr/bin/env bash
# agy-verify.sh — agy가 "다 했다"고 말한 것을 믿지 않고 실제로 확인한다.
#
#   tools/agy-verify.sh                     변경 요약만
#   tools/agy-verify.sh path1 path2 ...     지정 경로가 실제로 생겼는지까지
#
# agy는 작업을 안 하고도 "완료했습니다"라고 보고하는 경우가 있다.
# 이 스크립트는 파일시스템과 git을 근거로만 판단한다.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0

echo "════ 1. git 변경 내역 ════"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  CHANGED=$(git status --porcelain | wc -l)
  echo "변경된 경로: ${CHANGED}개"
  git status --short
  if [[ "$CHANGED" -eq 0 ]]; then
    echo "🔴 아무것도 바뀌지 않았다 — agy가 일을 하지 않았을 가능성이 높다"
    FAIL=1
  fi
  echo
  echo "── 추가/수정 줄 수 ──"
  git diff --stat
  git diff --cached --stat
else
  echo "⚠️ git 저장소가 아니다"
fi

echo
echo "════ 2. 최근 agy 로그 ════"
LOG=$(ls -t plan/agy-log/*.md 2>/dev/null | head -1)
if [[ -n "${LOG:-}" ]]; then
  echo "로그: $LOG  ($(stat -c %y "$LOG" | cut -d. -f1))"
  for PAT in "terminating .* background task" "no output produced" "auto-denied" "Error" "Traceback"; do
    if grep -qiE "$PAT" "$LOG"; then
      echo "🔴 로그에 '$PAT' 발견"
      grep -iE "$PAT" "$LOG" | head -3 | sed 's/^/     /'
      FAIL=1
    fi
  done
  if grep -q "CHANGED:" "$LOG"; then
    echo "── agy 자기 보고 ──"
    sed -n '/CHANGED:/,/^```/p' "$LOG" | head -20 | sed 's/^/     /'
  else
    echo "🔴 보고 형식(CHANGED:)이 없다 — 작업 미완 가능성"
    FAIL=1
  fi
else
  echo "⚠️ agy 로그가 없다"
fi

echo
echo "════ 3. 산출물 존재 확인 ════"
if [[ $# -eq 0 ]]; then
  echo "(확인할 경로를 인자로 주면 검사한다)"
else
  for P in "$@"; do
    if [[ -e "$P" ]]; then
      if [[ -f "$P" ]]; then
        SZ=$(stat -c %s "$P")
        if [[ "$SZ" -lt 10 ]]; then
          echo "🔴 $P — 존재하나 ${SZ}바이트 (빈 껍데기)"
          FAIL=1
        else
          echo "✅ $P (${SZ}바이트)"
        fi
      else
        N=$(find "$P" -type f | wc -l)
        if [[ "$N" -eq 0 ]]; then
          echo "🔴 $P/ — 디렉토리는 있으나 파일이 없다"
          FAIL=1
        else
          echo "✅ $P/ (파일 ${N}개)"
        fi
      fi
    else
      echo "🔴 $P — 없다"
      FAIL=1
    fi
  done
fi

echo
echo "════ 4. 하드 제약 위반 검사 ════"
VIOL=0
for PAT in bfloat16 flash_attn load_in_4bit load_in_8bit bitsandbytes; do
  HITS=$(grep -rln "$PAT" --include='*.py' --include='*.txt' --include='*.toml' . 2>/dev/null | grep -v '.venv\|node_modules\|/.git/' || true)
  if [[ -n "$HITS" ]]; then
    echo "🔴 Pascal 금지 패턴 '$PAT':"; echo "$HITS" | sed 's/^/     /'; VIOL=1; FAIL=1
  fi
done
HEX=$(grep -rln -E '#[0-9a-fA-F]{6}' --include='*.jsx' --include='*.tsx' frontend/src 2>/dev/null || true)
if [[ -n "$HEX" ]]; then
  echo "🟡 컴포넌트에 hex 색상 하드코딩 (tokens.css의 var(--…)를 쓸 것):"; echo "$HEX" | sed 's/^/     /'
fi
SEC=$(git ls-files 2>/dev/null | grep -E '^secrets/|^\.env$|^db_data/' || true)
if [[ -n "$SEC" ]]; then
  echo "🔴 시크릿/데이터가 git에 추적되고 있다:"; echo "$SEC" | sed 's/^/     /'; FAIL=1
fi
[[ $VIOL -eq 0 && -z "$SEC" ]] && echo "✅ 위반 없음"

echo
if [[ $FAIL -eq 1 ]]; then
  echo "════ 🔴 검증 실패 — agy의 보고를 그대로 믿지 말 것 ════"
  exit 1
fi
echo "════ ✅ 검증 통과 ════"
