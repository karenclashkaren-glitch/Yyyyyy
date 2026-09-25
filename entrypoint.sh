#!/usr/bin/env bash
set -euo pipefail

# Railway assigns PORT at runtime and routes its public HTTPS domain to it.
# Fall back to 8080 for local testing.
export PORT="${PORT:-8080}"

# Keep the same UUID across restarts by setting it as a Railway env var.
# If you don't set one, a new one is generated every deploy and printed below.
if [ -z "${UUID:-}" ]; then
  UUID="$(cat /proc/sys/kernel/random/uuid)"
  echo "############################################################"
  echo "No UUID env var set — generated a temporary one for this run:"
  echo "  UUID=${UUID}"
  echo "Set UUID as a Railway environment variable to keep it stable"
  echo "across redeploys and restarts."
  echo "############################################################"
fi
export UUID

export WSPATH="${WSPATH:-/vless}"

envsubst < /app/config.json.template > /app/config.json

echo "Starting sing-box"
echo "  listen_port: ${PORT}"
echo "  ws path:     ${WSPATH}"
echo "  uuid:        ${UUID}"

exec /usr/local/bin/sing-box run -c /app/config.json
