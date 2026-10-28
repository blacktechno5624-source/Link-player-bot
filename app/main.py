import logging
import os
import re
from contextlib import asynccontextmanager
from urllib.parse import urlencode, urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("link-player")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").strip().rstrip("/")
ALLOWED_USER_IDS = {
    int(x.strip()) for x in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if x.strip().isdigit()
}
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TG_APP = None

TERABOX_HOST_RE = re.compile(
    r"(^|\.)("
    r"terabox\.com|teraboxapp\.com|1024terabox\.com|1024tera\.com|"
    r"terabox\.app|freeterabox\.com|4funbox\.com|mirrobox\.com|"
    r"nephobox\.com|momerybox\.com|terasharelink\.com"
    r")$",
    re.IGNORECASE,
)

def is_allowed(user_id: int | None) -> bool:
    return not ALLOWED_USER_IDS or (user_id is not None and user_id in ALLOWED_USER_IDS)

def classify_url(raw: str) -> str:
    """Classify only. Does not fetch or claim that a URL is playable."""
    raw = raw.strip()
    if len(raw) > 4096:
        raise ValueError("Link bahut lamba hai.")
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Sirf valid HTTPS link accept hota hai.")
    host = parsed.hostname.lower().rstrip(".")
    if host == "terabox.com" or TERABOX_HOST_RE.search(host):
        return "terabox_share"
    path = parsed.path.lower()
    if path.endswith(".m3u8"):
        return "hls"
    if path.endswith((".mp4", ".m4v", ".webm", ".mov")):
        return "video"
    # Some signed URLs have no file extension. Don't guess their type.
    return "unknown"

def player_url(raw: str) -> str:
    return f"{PUBLIC_BASE_URL}/player?{urlencode({'url': raw})}"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_allowed(user.id if user else None):
        await update.effective_message.reply_text("Access restricted. Bot owner se access maangein.")
        return
    await update.effective_message.reply_text(
        "Namaste! 🎬\n\nApna authorized direct HTTPS MP4 ya HLS (.m3u8) link bhejein. "
        "Main player page ka button banaunga; video download/store nahi hoga.\n\n"
        "Note: TeraBox share link aur direct stream link alag hote hain. Is clean starter mein "
        "TeraBox share-link resolver configured nahi hai, isliye main uska fake playback link nahi banaunga."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_cmd(update, context)

async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not is_allowed(user.id if user else None):
        await msg.reply_text("Access restricted. Bot owner se access maangein.")
        return
    raw = (msg.text or "").strip()
    try:
        kind = classify_url(raw)
    except ValueError as exc:
        await msg.reply_text(f"Link check fail: {exc}")
        return

    if kind == "terabox_share":
        await msg.reply_text(
            "Ye TeraBox share link hai, verified direct video URL nahi. ❗\n\n"
            "Is build mein arbitrary TeraBox share-link resolution implemented nahi hai. "
            "TeraBox ka documented streaming flow account access token + file path use karta hai; "
            "public share URL se direct HLS banane ka daava karna galat hoga.\n\n"
            "Aapka own direct MP4/HLS URL ho to bhejein, ya supported/authorized resolver API ki documentation dein."
        )
        return
    if kind == "unknown":
        await msg.reply_text(
            "URL HTTPS hai, lekin uska media type confirm nahi ho saka. "
            "Fake playable status nahi dunga. Direct .mp4 ya .m3u8 URL bhejein."
        )
        return

    url = player_url(raw)
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("▶️ Play Video", url=url)]])
    await msg.reply_text(
        f"Link format check pass hua ({'HLS' if kind == 'hls' else 'video URL'}). "
        "Source server par playback abhi independently verify nahi hua.\n\n"
        "Play button dabakar browser player kholein.",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    global TG_APP
    if BOT_TOKEN:
        TG_APP = Application.builder().token(BOT_TOKEN).build()
        TG_APP.add_handler(CommandHandler("start", start_cmd))
        TG_APP.add_handler(CommandHandler("help", help_cmd))
        TG_APP.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, link_handler))
        await TG_APP.initialize()
        await TG_APP.start()
        await TG_APP.updater.start_polling(drop_pending_updates=False)
        log.info("Telegram polling started")
    else:
        log.warning("BOT_TOKEN is missing; web player starts, Telegram bot stays disabled")
    yield
    if TG_APP:
        await TG_APP.updater.stop()
        await TG_APP.stop()
        await TG_APP.shutdown()

app = FastAPI(title="Link Player Bot", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/player", response_class=HTMLResponse)
async def player(url: str = Query(..., min_length=8, max_length=4096)):
    try:
        kind = classify_url(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if kind == "terabox_share":
        raise HTTPException(status_code=422, detail="TeraBox share resolution is not configured; no fake stream URL was generated.")
    if kind not in ("hls", "video"):
        raise HTTPException(status_code=422, detail="Only direct HTTPS MP4/video or .m3u8 URLs are supported in this build.")
    # URL is inserted as a data attribute by URL-encoding it, not HTML interpolation.
    from html import escape
    safe_url = escape(url, quote=True)
    safe_kind = "hls" if kind == "hls" else "video"
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Online Video Player</title><link rel="stylesheet" href="/static/style.css">
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.18/dist/hls.min.js"></script></head>
<body><main class="shell"><header><div class="logo">▶</div><div><h1>Online Video Player</h1><p>Source-hosted playback · no server-side video storage</p></div></header>
<section class="player-card"><video id="video" controls playsinline preload="metadata" data-url="{safe_url}" data-kind="{safe_kind}"></video>
<div id="status" role="status">Loading player…</div>
<p class="note">Playback depends on the source host, link validity, browser support and CORS settings.</p></section>
<a class="back" href="/">← Open another link</a></main><script src="/static/player.js"></script></body></html>"""
    return HTMLResponse(page)

@app.get("/healthz")
async def healthz():
    return JSONResponse({"status": "ok", "telegram_configured": bool(BOT_TOKEN), "resolver": "direct-media-only"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
