#!/usr/bin/env bash
set -euo pipefail

mkdir -p /tmp/tordata

if command -v tor >/dev/null 2>&1; then
  if ! python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',9050)); s.close()" 2>/dev/null; then
    tor \
      --RunAsDaemon 1 \
      --SocksPort 127.0.0.1:9050 \
      --ControlPort 127.0.0.1:9051 \
      --CookieAuthentication 0 \
      --DataDirectory /tmp/tordata \
      --Log "notice file /tmp/tor.log" || true
    for _ in $(seq 1 25); do
      if python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',9050)); s.close()" 2>/dev/null; then
        break
      fi
      sleep 1
    done
  fi
fi

exec streamlit run web_app.py \
  --server.port="${PORT:-8501}" \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
