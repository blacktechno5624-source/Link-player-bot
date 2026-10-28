# Link Player Bot — clean starter

A new, separate Telegram bot + browser player. No old project files are reused.

## Honest scope
- Working baseline: Telegram bot accepts direct HTTPS MP4/HLS URLs and creates a player link.
- Web player: HTML5 MP4 playback and HLS playback through hls.js.
- Does **not** pretend a TeraBox share URL is a direct stream URL.
- TeraBox public-share resolution is not implemented because a verified, supported resolver/API for that workflow has not been configured. TeraBox's documented OpenAPI streaming example uses an account access token plus a file path; that is a different flow from resolving an arbitrary share URL.
- No media is downloaded or stored by this app. Playback happens from the source URL in the user's browser. The source provider may still impose its own limits/CORS/token expiry.

## Files
- `app/main.py` — FastAPI web app + Telegram polling bot
- `app/static/index.html` — player UI
- `requirements.txt` — Python dependencies
- `render.yaml` — Render blueprint
- `.env.example` — local configuration template

## Local run
1. Install Python 3.11+.
2. Create a Telegram bot using BotFather and copy its token.
3. Copy `.env.example` to `.env` and fill `BOT_TOKEN` and `PUBLIC_BASE_URL`.
4. Install dependencies: `pip install -r requirements.txt`
5. Run: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
6. Set `PUBLIC_BASE_URL=http://127.0.0.1:8000` for local browser tests. Telegram cannot open your local machine unless you expose it with a secure tunnel.

## Render deployment
1. Push this folder to a **new** GitHub repository.
2. In Render, create a Web Service from that repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `BOT_TOKEN` = token from BotFather
   - `PUBLIC_BASE_URL` = your deployed HTTPS Render URL, e.g. `https://your-service.onrender.com`
   - `ALLOWED_USER_IDS` = optional comma-separated Telegram numeric user IDs; leave blank to allow any user
6. Deploy. Open `/healthz`; expect `{"status":"ok","telegram_configured":true}` when token is present.
7. Send `/start` to the bot, then test using a direct HTTPS MP4/HLS link that you own or are authorized to stream.

## Important free-hosting limitations
- Render free services may sleep when idle, causing a cold start.
- Third-party source links can expire or block browser playback.
- HLS sources may require CORS headers from the media host. This app cannot override a source server's CORS policy.
- Never paste bot tokens or account cookies into public chats or source code.
