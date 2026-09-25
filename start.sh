#!/usr/bin/env bash
set -euo pipefail

# Railway assigns PORT at runtime and routes its public HTTPS domain to it.
export PORT="${PORT:-8080}"

# --- VLESS UUID -------------------------------------------------------
if [ -z "${UUID:-}" ]; then
  UUID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
  echo "############################################################"
  echo "No UUID set - generated one for this run:"
  echo "  UUID=${UUID}"
  echo "Set it as a Railway variable to keep it stable across deploys."
  echo "############################################################"
fi
export UUID

export WSPATH="${WSPATH:-/vless}"

# --- Subscription token -------------------------------------------------
if [ -z "${SUBTOKEN:-}" ]; then
  SUBTOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  echo "############################################################"
  echo "No SUBTOKEN set - generated one for this run:"
  echo "  SUBTOKEN=${SUBTOKEN}"
  echo "This changes on every restart unless you set it as a Railway"
  echo "variable - do that, or saved subscription URLs will break."
  echo "############################################################"
fi
export SUBTOKEN

# --- Panel credentials ----------------------------------------------------
export PANEL_USERNAME="${PANEL_USERNAME:-admin}"

if [ -z "${PANEL_PASSWORD:-}" ]; then
  PANEL_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(12))')"
  echo "############################################################"
  echo "No PANEL_PASSWORD set - generated one for this run:"
  echo "  PANEL_USERNAME=${PANEL_USERNAME}"
  echo "  PANEL_PASSWORD=${PANEL_PASSWORD}"
  echo "Set both as Railway variables to keep them stable across deploys."
  echo "############################################################"
fi
export PANEL_PASSWORD

# --- Render configs from templates ----------------------------------------
envsubst '${UUID} ${WSPATH}' < /app/config.json.template > /app/config.json
envsubst '${PORT} ${WSPATH}' < /app/nginx.conf.template > /app/nginx.conf

echo "Starting sing-box (127.0.0.1:10000), panel (127.0.0.1:10001), nginx (public :${PORT})"

/usr/local/bin/sing-box run -c /app/config.json &
SINGBOX_PID=$!

python3 /app/panel/server.py &
PANEL_PID=$!

nginx -c /app/nginx.conf -g 'daemon off;' &
NGINX_PID=$!

trap 'kill -TERM $SINGBOX_PID $PANEL_PID $NGINX_PID 2>/dev/null || true' TERM INT

wait -n "$SINGBOX_PID" "$PANEL_PID" "$NGINX_PID"
CODE=$?
echo "A process exited (code $CODE) - stopping the others so Railway restarts the service"
kill "$SINGBOX_PID" "$PANEL_PID" "$NGINX_PID" 2>/dev/null || true
exit "$CODE"
