#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${PORT:-8100}"
LOG_FILE="$SCRIPT_DIR/uvicorn.log"

# Git Bash's $! is an MSYS-internal pid, not the real Windows pid taskkill
# needs, so we identify our process by asking netstat who owns the port
# instead (its last column on a LISTENING line is the real Windows PID).
kill_port() {
  local port_pids
  port_pids="$(netstat -ano 2>/dev/null | grep "LISTENING" | grep ":$PORT " | awk '{print $NF}' | sort -u || true)"
  for p in $port_pids; do
    echo "포트 $PORT 점유 중인 프로세스(PID $p) 종료 중..."
    taskkill //PID "$p" //T //F >/dev/null 2>&1 || true
  done
}

start_server() {
  if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "가상환경(.venv)이 없습니다. 먼저 다음을 실행하세요:" >&2
    echo "  python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements.txt" >&2
    exit 1
  fi

  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.venv/Scripts/activate"
  echo "JobFit 서버 시작 중... (포트 $PORT, http://127.0.0.1:$PORT)"
  # 포그라운드로 실행 (nohup/disown 없음): 이 터미널을 닫거나 Ctrl+C 하면
  # 서버도 함께 종료된다. 로그는 터미널에 그대로 출력되면서 파일에도 남는다.
  uvicorn app.main:app --reload --port "$PORT" 2>&1 | tee "$LOG_FILE"
}

kill_port
start_server
