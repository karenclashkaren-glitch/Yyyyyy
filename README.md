# sing-box (VLESS+WS) on Railway

A minimal sing-box server, packaged to deploy on Railway straight from GitHub.
It runs VLESS over WebSocket with no TLS inside the container — Railway's
edge proxy terminates HTTPS for you and forwards plain traffic in, so this
works out of the box on Railway's free public domain.

## 1. Push to GitHub

Upload this folder as a new GitHub repo (or unzip it into an existing one).

## 2. Deploy on Railway

1. Railway dashboard → **New Project** → **Deploy from GitHub repo** → pick
   the repo.
2. Railway will detect the `Dockerfile` and build automatically. No other
   build settings are needed.
3. Once deployed, open the service → **Settings → Networking** → **Generate
   Domain**. Railway gives you a public `*.up.railway.app` domain with a
   free TLS certificate already attached, and Railway itself provides the
   `PORT` your container listens on.

## 3. Set a stable UUID (recommended)

Without a `UUID` env var, the server generates a random one on every
restart, which breaks your client config each time. Set it once:

1. Generate a UUID (e.g. `uuidgen`, or any online UUIDv4 generator).
2. Service → **Variables** → add `UUID` = `<your-uuid>`.
3. Redeploy.

Optional: `WSPATH` (default `/vless`) — the WebSocket path, change it to
anything if you want.

## 4. Client configuration

You'll need, from Railway:
- **Address**: your `*.up.railway.app` domain
- **Port**: `443`
- **UUID**: the one you set above
- **Network**: `ws` (WebSocket)
- **Path**: `/vless` (or your custom `WSPATH`)
- **TLS**: on, SNI = same domain

As a share link for apps like v2rayN, v2rayNG, NekoBox, or Shadowrocket:

```
vless://UUID@your-app.up.railway.app:443?encryption=none&security=tls&type=ws&host=your-app.up.railway.app&path=%2Fvless&sni=your-app.up.railway.app#railway-vless
```

Replace `UUID` and `your-app.up.railway.app` with your actual values, and
`%2Fvless` with your URL-encoded path if you changed `WSPATH`.

Or as a sing-box client outbound:

```json
{
  "type": "vless",
  "tag": "proxy",
  "server": "your-app.up.railway.app",
  "server_port": 443,
  "uuid": "UUID",
  "tls": {
    "enabled": true,
    "server_name": "your-app.up.railway.app"
  },
  "transport": {
    "type": "ws",
    "path": "/vless"
  }
}
```

## Files

- `Dockerfile` — installs the latest sing-box release at build time
- `config.json.template` — server config, filled in with env vars at startup
- `entrypoint.sh` — renders the config and starts sing-box
- `railway.toml` — tells Railway explicitly to use the Dockerfile builder

## Notes

- Railway's free tier has usage limits and isn't meant for heavy, sustained
  proxy traffic — fine for personal use, but check their current
  [pricing/limits](https://railway.com/pricing) if you plan to use it a lot.
- Using a service like this to access the open internet for yourself is
  routine; using it to intercept or relay other people's traffic without
  consent is not — keep the UUID private since anyone with it can use your
  server.
