#!/usr/bin/env python3
"""Minimal management panel for the sing-box VLESS deployment.

Serves:
  GET  /             - HTML dashboard (Basic Auth required)
  POST /             - update the in-memory clean-IP list (Basic Auth required)
  GET  /api/config   - JSON config incl. all links (Basic Auth required)
  GET  /sub/<token>  - base64 subscription content, one link per line (no auth; token is the secret)
  GET  /healthz      - plain 200, for manual checks

Runs on 127.0.0.1 only - nginx is the public-facing process.

"Clean IPs": VLESS+WS+TLS lets you dial a different IP than the one your
TLS SNI / Host header claims - the edge network routes on SNI/Host, not on
which of its IPs you connected to. If your ISP throttles some of Railway's
edge IPs but not others, pointing the client at an unblocked ("clean") IP
while keeping SNI/Host set to your Railway domain still reaches the same
place. This panel lets you paste a batch of such IPs and get one link per
IP, all sharing your UUID/domain/path, so a client can try each.
"""
import base64
import hmac
import html
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote

UUID = os.environ.get("UUID", "")
WSPATH = os.environ.get("WSPATH", "/vless")
SUBTOKEN = os.environ.get("SUBTOKEN", "")
PANEL_USERNAME = os.environ.get("PANEL_USERNAME", "admin")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
PANEL_PORT = int(os.environ.get("PANEL_INTERNAL_PORT", "10001"))

DEFAULT_DOMAIN = "your-app.up.railway.app"

# In-memory clean-IP list. Seeded from the CLEAN_IPS env var at startup
# (survives restarts if you set it as a Railway variable), editable live
# from the dashboard (that edit does NOT survive a restart - re-paste it,
# or update the env var too, once you've settled on a working list).
_state_lock = threading.Lock()
_clean_ips_raw = os.environ.get("CLEAN_IPS", "")


def parse_clean_ips(raw: str):
    """Parse '<ip>' or '<ip>:<port>' entries, one per comma/space/newline."""
    entries = []
    for part in re.split(r"[,\s]+", raw.strip()):
        if not part:
            continue
        if ":" in part:
            ip, _, port = part.partition(":")
            port = port.strip() or "443"
        else:
            ip, port = part, "443"
        ip = ip.strip()
        if ip:
            entries.append((ip, port))
    return entries


def vless_link(domain: str, address: str = None, port: str = "443", label: str = "railway") -> str:
    addr = address or domain
    path_q = quote(WSPATH, safe="")
    tag_q = quote(label, safe="")
    return (
        f"vless://{UUID}@{addr}:{port}"
        f"?encryption=none&security=tls&type=ws"
        f"&host={domain}&path={path_q}&sni={domain}"
        f"#{tag_q}"
    )


def all_links(domain: str):
    """Primary domain link first, then one per configured clean IP."""
    links = [("primary", vless_link(domain, label="railway"))]
    with _state_lock:
        ips = parse_clean_ips(_clean_ips_raw)
    for ip, port in ips:
        label = f"railway-{ip}"
        links.append((f"{ip}:{port}", vless_link(domain, address=ip, port=port, label=label)))
    return links


def render_dashboard(domain: str, links, sub_url: str, saved: bool = False) -> str:
    safe_domain = html.escape(domain)
    safe_uuid = html.escape(UUID)
    safe_path = html.escape(WSPATH)
    safe_sub = html.escape(sub_url)
    primary_link = html.escape(links[0][1])
    clean_links = links[1:]

    with _state_lock:
        raw_ips = _clean_ips_raw
    safe_raw_ips = html.escape(raw_ips)

    clean_rows = ""
    for label, link in clean_links:
        safe_label = html.escape(label)
        safe_link_val = html.escape(link)
        row_id = f"ip-{html.escape(quote(label, safe=''))}"
        clean_rows += f"""
    <div class="row" style="margin-bottom:8px">
      <input readonly id="{row_id}" value="{safe_link_val}" style="font-size:12px">
      <button onclick="copyField('{row_id}', this)">Copy</button>
    </div>
    <div class="ip-label">{safe_label}</div>
"""

    clean_section = f"""
  <div class="card">
    <h2>Clean IP servers ({len(clean_links)})</h2>
    {clean_rows if clean_rows else '<div class="note">None configured yet - add some below.</div>'}
  </div>
""" if True else ""

    saved_banner = '<div class="banner">Clean IP list updated.</div>' if saved else ""

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
  textarea {{
    width: 100%; min-height: 120px; background: #0f1115; border: 1px solid #262b36;
    color: #e6e6e6; border-radius: 8px; padding: 10px 12px; font-size: 13px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; resize: vertical;
  }}
  button {{
    background: #3b82f6; color: white; border: none; border-radius: 8px;
    padding: 10px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
    flex-shrink: 0;
  }}
  button.secondary {{ background: #2a2f3a; }}
  button:active {{ opacity: .8; }}
  .field {{ margin-bottom: 10px; font-size: 13px; }}
  .field b {{ color: #9aa0ab; font-weight: 500; }}
  #qrcode {{ display: flex; justify-content: center; padding: 12px; background: #fff; border-radius: 8px; }}
  .note {{ font-size: 12px; color: #9aa0ab; margin-top: 8px; line-height: 1.5; }}
  .ip-label {{ font-size: 11px; color: #6b7280; margin: -4px 0 10px 2px; }}
  .banner {{
    background: #14301f; border: 1px solid #1f5c37; color: #86efac;
    padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 16px;
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>sing-box panel</h1>
  <div class="sub">{safe_domain}</div>
  {saved_banner}

  <div class="card">
    <h2>Server</h2>
    <div class="field"><b>UUID:</b> {safe_uuid}</div>
    <div class="field"><b>Path:</b> {safe_path}</div>
    <div class="field"><b>Port:</b> 443 (TLS, via Railway)</div>
  </div>

  <div class="card">
    <h2>Primary VLESS link</h2>
    <div class="row">
      <input readonly id="link" value="{primary_link}">
      <button onclick="copyField('link', this)">Copy</button>
    </div>
    <div id="qrcode" style="margin-top:12px"></div>
  </div>

  {clean_section}

  <div class="card">
    <h2>Add / update clean IPs</h2>
    <form method="POST" action="/">
      <textarea name="clean_ips" placeholder="One per line, IP or IP:PORT&#10;e.g.&#10;104.16.1.1&#10;104.16.2.2:8443">{safe_raw_ips}</textarea>
      <div style="margin-top:10px">
        <button type="submit">Save</button>
      </div>
    </form>
    <div class="note">
      Each IP gets its own link with the same UUID, domain, and path -
      only the connect address changes. Clients keep TLS SNI / the WS Host
      header set to your domain, so routing still lands on this service.
      This list lives in memory and resets on restart; set it as the
      <code>CLEAN_IPS</code> Railway variable too if you want it to persist.
    </div>
  </div>

  <div class="card">
    <h2>Subscription URL</h2>
    <div class="row">
      <input readonly id="sub" value="{safe_sub}">
      <button onclick="copyField('sub', this)">Copy</button>
    </div>
    <div class="note">
      Includes the primary link plus every clean IP above, one per line,
      base64-encoded. Paste this into your client's "subscribe" / "import
      from URL" field instead of a single link.
    </div>
  </div>

  <div class="note">
    Changing UUID, WSPATH, SUBTOKEN or the panel credentials requires
    setting them as Railway service variables and redeploying.
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
    server_version = "singbox-panel/1.1"

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
            links = all_links(domain)
            content = "\n".join(link for _, link in links) + "\n"
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            self._send(200, "text/plain; charset=utf-8", b64)
            return

        if not self._check_auth():
            self._require_auth()
            return

        domain = self._domain()
        links = all_links(domain)
        sub_url = f"https://{domain}/sub/{SUBTOKEN}"

        if path == "/api/config":
            body = json.dumps({
                "uuid": UUID,
                "path": WSPATH,
                "domain": domain,
                "sub_link": sub_url,
                "links": [{"label": label, "link": link} for label, link in links],
            }, indent=2)
            self._send(200, "application/json", body)
            return

        self._send(200, "text/html; charset=utf-8", render_dashboard(domain, links, sub_url))

    def do_POST(self):
        path = self.path.split("?", 1)[0]

        if not self._check_auth():
            self._require_auth()
            return

        if path != "/":
            self._send(404, "text/plain", "not found")
            return

        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
        fields = parse_qs(body)
        new_ips = fields.get("clean_ips", [""])[0]

        global _clean_ips_raw
        with _state_lock:
            _clean_ips_raw = new_ips

        domain = self._domain()
        links = all_links(domain)
        sub_url = f"https://{domain}/sub/{SUBTOKEN}"
        self._send(200, "text/html; charset=utf-8", render_dashboard(domain, links, sub_url, saved=True))

    def log_message(self, fmt, *args):
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
