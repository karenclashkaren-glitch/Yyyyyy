#!/usr/bin/env python3
"""Minimal management panel for the sing-box VLESS deployment.

Serves:
  GET /             - HTML dashboard (Basic Auth required)
  GET /api/config   - JSON config (Basic Auth required)
  GET /sub/<token>  - base64 subscription content (no auth; token is the secret)
  GET /healthz      - plain 200, for manual checks

Runs on 127.0.0.1 only - nginx is the public-facing process.
"""
import base64
import hmac
import html
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

UUID = os.environ.get("UUID", "")
WSPATH = os.environ.get("WSPATH", "/vless")
SUBTOKEN = os.environ.get("SUBTOKEN", "")
PANEL_USERNAME = os.environ.get("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
PANEL_PORT = int(os.environ.get("PANEL_INTERNAL_PORT", "10001"))

DEFAULT_DOMAIN = "your-app.up.railway.app"


def vless_link(domain: str) -> str:
    path_q = quote(WSPATH, safe="")
    return (
        f"vless://{UUID}@{domain}:443"
        f"?encryption=none&security=tls&type=ws"
        f"&host={domain}&path={path_q}&sni={domain}"
        f"#railway-vless"
    )


def render_dashboard(domain: str, link: str, sub_url: str) -> str:
    safe_link = html.escape(link)
    safe_sub = html.escape(sub_url)
    safe_uuid = html.escape(UUID)
    safe_path = html.escape(WSPATH)
    safe_domain = html.escape(domain)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>sing-box panel</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 16px 48px;
    background: #0f1115; color: #e6e6e6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }}
  .wrap {{ max-width: 640px; margin: 0 auto; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  .sub {{ color: #9aa0ab; font-size: 13px; margin-bottom: 24px; }}
  .card {{
    background: #171a21; border: 1px solid #262b36; border-radius: 12px;
    padding: 16px; margin-bottom: 16px;
  }}
  .card h2 {{ font-size: 14px; color: #9aa0ab; margin: 0 0 10px; text-transform: uppercase; letter-spacing: .04em; }}
  .row {{ display: flex; gap: 8px; align-items: center; }}
  input[readonly] {{
    flex: 1; min-width: 0; background: #0f1115; border: 1px solid #262b36;
    color: #e6e6e6; border-radius: 8px; padding: 10px 12px; font-size: 13px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }}
  button {{
    background: #3b82f6; color: white; border: none; border-radius: 8px;
    padding: 10px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
    flex-shrink: 0;
  }}
  button:active {{ opacity: .8; }}
  .field {{ margin-bottom: 10px; font-size: 13px; }}
  .field b {{ color: #9aa0ab; font-weight: 500; }}
  #qrcode {{ display: flex; justify-content: center; padding: 12px; background: #fff; border-radius: 8px; }}
  .note {{ font-size: 12px; color: #9aa0ab; margin-top: 8px; line-height: 1.5; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>sing-box panel</h1>
  <div class="sub">{safe_domain}</div>

  <div class="card">
    <h2>Server</h2>
    <div class="field"><b>UUID:</b> {safe_uuid}</div>
    <div class="field"><b>Path:</b> {safe_path}</div>
    <div class="field"><b>Port:</b> 443 (TLS, via Railway)</div>
  </div>

  <div class="card">
    <h2>VLESS link</h2>
    <div class="row">
      <input readonly id="link" value="{safe_link}">
      <button onclick="copyField('link', this)">Copy</button>
    </div>
    <div id="qrcode" style="margin-top:12px"></div>
  </div>

  <div class="card">
    <h2>Subscription URL</h2>
    <div class="row">
      <input readonly id="sub" value="{safe_sub}">
      <button onclick="copyField('sub', this)">Copy</button>
    </div>
    <div class="note">
      Paste this into your client's "subscription" / "import from URL" field
      (v2rayN, v2rayNG, NekoBox, Shadowrocket, etc). It returns a base64 list
      of server links so the app can refresh them without you re-pasting.
    </div>
  </div>

  <div class="note">
    Changing UUID, WSPATH, SUBTOKEN or the panel credentials requires setting
    them as Railway service variables and redeploying — this panel is
    read-only.
  </div>
</div>
<script>
  new QRCode(document.getElementById("qrcode"), {{
    text: document.getElementById("link").value,
    width: 200, height: 200
  }});
  function copyField(id, btn) {{
    const el = document.getElementById(id);
    el.select();
    navigator.clipboard.writeText(el.value).then(() => {{
      const orig = btn.textContent;
      btn.textContent = "Copied";
      setTimeout(() => btn.textContent = orig, 1200);
    }});
  }}
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "singbox-panel/1.0"

    def _domain(self) -> str:
        host = self.headers.get("Host", "")
        return host.split(":")[0] if host else DEFAULT_DOMAIN

    def _check_auth(self) -> bool:
        if not PANEL_PASSWORD:
            return False
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Basic "):
            return False
        try:
            decoded = base64.b64decode(auth[6:]).decode("utf-8")
            user, _, pw = decoded.partition(":")
        except Exception:
            return False
        return hmac.compare_digest(user, PANEL_USERNAME) and hmac.compare_digest(pw, PANEL_PASSWORD)

    def _require_auth(self):
        self._send(401, "text/plain", "Authentication required", extra_headers={
            "WWW-Authenticate": 'Basic realm="sing-box panel"'
        })

    def _send(self, code, ctype, body, extra_headers=None):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/healthz":
            self._send(200, "text/plain", "ok")
            return

        if path.startswith("/sub/"):
            token = path[len("/sub/"):]
            if not SUBTOKEN or not hmac.compare_digest(token, SUBTOKEN):
                self._send(404, "text/plain", "not found")
                return
            domain = self._domain()
            content = vless_link(domain) + "\n"
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            self._send(200, "text/plain; charset=utf-8", b64)
            return

        if not self._check_auth():
            self._require_auth()
            return

        domain = self._domain()
        link = vless_link(domain)
        sub_url = f"https://{domain}/sub/{SUBTOKEN}"

        if path == "/api/config":
            body = json.dumps({
                "uuid": UUID,
                "path": WSPATH,
                "domain": domain,
                "vless_link": link,
                "sub_link": sub_url,
            }, indent=2)
            self._send(200, "application/json", body)
            return

        self._send(200, "text/html; charset=utf-8", render_dashboard(domain, link, sub_url))

    def log_message(self, fmt, *args):
        # Keep default stderr logging (captured by Railway's log stream)
        super().log_message(fmt, *args)


def main():
    if not UUID:
        print("panel: WARNING - UUID is not set")
    if not SUBTOKEN:
        print("panel: WARNING - SUBTOKEN is not set, /sub links are disabled")
    if not PANEL_PASSWORD:
        print("panel: WARNING - PANEL_PASSWORD is not set, dashboard is inaccessible")

    server = ThreadingHTTPServer(("127.0.0.1", PANEL_PORT), Handler)
    print(f"panel: listening on 127.0.0.1:{PANEL_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
