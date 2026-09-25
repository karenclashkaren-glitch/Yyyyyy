# sing-box (VLESS+WS) + management panel, on Railway

A single Railway service that runs three processes behind one public port:

- **nginx** — the only process bound to Railway's public `$PORT`. Splits
  traffic by path: the VLESS WebSocket path goes to sing-box, everything
  else goes to the panel.
- **sing-box** — VLESS over WebSocket, listening on `127.0.0.1:10000`
  (not directly reachable from outside the container).
- **panel** — a small Python web dashboard on `127.0.0.1:10001` showing
  your current config, a QR code, and a subscription link.

Railway only gives one public domain per service and doesn't let two ports
share it, so nginx is what makes a single domain serve both the proxy and
the panel.

## 1. Push to GitHub

Upload this folder as a new GitHub repo (or unzip it into an existing one).

## 2. Deploy on Railway

1. Railway dashboard → **New Project** → **Deploy from GitHub repo** → pick
   the repo. Railway detects the `Dockerfile` and builds automatically.
2. Once deployed, open the service → **Settings → Networking** → **Generate
   Domain**. This is the one domain everything — proxy and panel — will
   live on.

## 3. Set variables (recommended before your first real use)

Without these, the server still works, but secrets regenerate on every
restart — annoying at best, and it invalidates any saved client config or
subscription URL. Service → **Variables**:

| Variable         | Purpose                                   | Default if unset       |
|------------------|--------------------------------------------|-------------------------|
| `UUID`           | VLESS client identity                      | random, regenerates each restart |
| `SUBTOKEN`       | Secret in the `/sub/<token>` URL           | random, regenerates each restart |
| `PANEL_USERNAME` | Dashboard login username                   | `admin` |
| `PANEL_PASSWORD` | Dashboard login password                   | random, regenerates each restart |
| `WSPATH`         | VLESS WebSocket path                       | `/vless` |
| `CLEAN_IPS`      | Seed list of clean IPs (see below)         | empty |

Generate a UUID with `uuidgen` or any UUIDv4 generator. For `SUBTOKEN` and
`PANEL_PASSWORD`, any long random string works.

If you skip this, check the deploy logs after the first boot — the
generated values are printed there.

## 4. Use the panel

Visit `https://<your-domain>/` and log in with `PANEL_USERNAME` /
`PANEL_PASSWORD` (HTTP Basic Auth). You'll see:

- Your current UUID, path, and the full `vless://` link
- A QR code for mobile clients (v2rayNG, Shadowrocket, etc. can scan it
  directly)
- A **subscription URL** (`https://<domain>/sub/<SUBTOKEN>`) — paste this
  into a client's "subscribe" / "import from URL" field instead of the raw
  link. The client can then refresh from it later instead of you re-pasting
  a link by hand.

The `/sub/` endpoint itself needs no login (subscription-fetching apps
don't send credentials) — its security is the random token in the URL, so
treat that URL like a password. Don't post it publicly.

## Clean IPs

VLESS+WS+TLS lets a client dial one IP while its TLS SNI and WS Host header
say another — the edge routes on SNI/Host, not on which IP you connected
to. If your ISP throttles some of Railway's edge IPs but not others,
pointing at an unblocked ("clean") one while keeping SNI/Host set to your
Railway domain still reaches this service.

Paste a batch of IPs (one per line, `ip` or `ip:port`) into the "Add /
update clean IPs" box on the dashboard and save. Each one gets its own
link — same UUID, domain, and path, just a different connect address — and
all of them (plus the primary domain link) are included in the
subscription URL, so a client can try each and use whichever works.

That list lives in memory and resets if the service restarts; set it as
the `CLEAN_IPS` variable too (same format) if you want it to survive
redeploys.

## Files

- `Dockerfile` — installs sing-box, nginx, python3
- `start.sh` — generates secrets, renders configs, runs all three processes
- `config.json.template` — sing-box config (internal-only listener)
- `nginx.conf.template` — path-based routing on the public port
- `panel/server.py` — the dashboard + subscription endpoint (stdlib only)
- `railway.toml` — tells Railway to use the Dockerfile builder

## Notes

- The UUID, path, subscription token, and panel login are read-only in the
  panel — change those via Railway variables and redeploy. Only the clean
  IP list is editable live.
- Railway's free tier has usage limits and isn't meant for heavy, sustained
  proxy traffic — fine for personal use; check current
  [pricing/limits](https://railway.com/pricing) if you'll use it a lot.
- Anyone with your subscription URL or VLESS link can use your server as
  their own exit node. Keep both, and the panel password, private.
