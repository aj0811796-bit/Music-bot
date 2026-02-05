import os
import asyncio
import logging
import sys
from collections import deque
from typing import Dict, List, Optional

# Configure for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Get from Railway environment variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
PORT = int(os.getenv("PORT", 8000))

# Validate
if not all([API_ID, API_HASH, BOT_TOKEN, SESSION_STRING]):
    logger.error("Missing environment variables!")
    sys.exit(1)

# Telegram imports
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

# Try to import pytgcalls with fallback
try:
    # Use pytgcalls v3.0.0
from pytgcalls import PyTgCalls
try:
    from pytgcalls.types import AudioPiped, AudioParameters
    from pytgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
except ImportError:
    # Fallback for older versions
    from pytgcalls.types.input_stream import AudioPiped, AudioParameters
    from pytgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
    logger.info("Using pytgcalls")
except ImportError:
    try:
        from py_tgcalls import PyTgCalls
        from py_tgcalls.types import AudioPiped, AudioParameters
        from py_tgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
        logger.info("Using py-tgcalls")
    except ImportError as e:
        logger.error(f"Failed to import voice call library: {e}")
        logger.error("Install with: pip install pytgcalls or pip install py-tgcalls")
        sys.exit(1)

# YouTube imports
from youtubesearchpython import VideosSearch
import yt_dlp

# FastAPI for health checks
from fastapi import FastAPI
import uvicorn
from threading import Thread

# Initialize FastAPI
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "online", "service": "telegram-music-bot"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

def run_web():
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

# Data storage
queues: Dict[int, deque] = {}
now_playing: Dict[int, Dict] = {}
loop_mode: Dict[int, bool] = {}

# Initialize clients
bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    parse_mode=ParseMode.MARKDOWN
)

user_client = Client(
    "music_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

call = PyTgCalls(user_client)

# Helper functions (keep your existing functions)
def get_queue(chat_id: int) -> deque:
    if chat_id not in queues:
        queues[chat_id] = deque(maxlen=50)
    return queues[chat_id]

async def search_youtube(query: str) -> Optional[str]:
    try:
        search = VideosSearch(query, limit=1)
        results = search.result().get("result", [])
        if results:
            return f"https://youtube.com/watch?v={results[0]['id']}"
    except Exception as e:
        logger.error(f"Search error: {e}")
    return None

async def get_stream_url(url: str) -> Optional[Dict]:
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
            
            if audio_formats:
                best_audio = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                audio_url = best_audio['url']
            else:
                audio_url = info.get('url', '')
            
            return {
                'title': info.get('title', 'Unknown'),
                'url': audio_url,
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
            }
    except Exception as e:
        logger.error(f"Stream URL error: {e}")
        return None

async def play_next(chat_id: int):
    try:
        queue = get_queue(chat_id)
        if queue:
            song = queue.popleft()
            await play_song(chat_id, song)
        else:
            now_playing.pop(chat_id, None)
            await bot.send_message(chat_id, "✅ Queue finished!")
    except Exception as e:
        logger.error(f"Play next error: {e}")

async def play_song(chat_id: int, song: Dict):
    try:
        now_playing[chat_id] = song
        
        audio = AudioPiped(
            song['url'],
            AudioParameters.from_quality("high"),
            additional_ffmpeg_parameters="-b:a 320k"
        )
        
        try:
            await call.join_group_call(chat_id, audio)
        except (GroupCallNotFound, NoActiveGroupCall):
            await bot.send_message(chat_id, "❌ Start voice chat first!")
            return
        except Exception as e:
            logger.error(f"Join error: {e}")
            await call.change_stream(chat_id, audio)
        
        await bot.send_message(
            chat_id,
            f"🎵 **Now Playing:** {song['title']}"
        )
        
    except Exception as e:
        logger.error(f"Play song error: {e}")
        await play_next(chat_id)

# Bot commands (keep your existing commands)
@bot.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Online!**\n\n"
        "**Commands:**\n"
        "/play [song] - Play music\n"
        "/splay [query] - Search & play\n"
        "/queue - Show queue\n"
        "/pause - Pause\n"
        "/resume - Resume\n"
        "/skip - Skip\n"
        "/stop - Stop\n"
        "/loop - Loop mode\n"
        "/volume [1-200] - Volume\n"
        "/clear - Clear queue"
    )

# Keep all your other command handlers...

@call.on_stream_end()
async def stream_end(chat_id: int):
    logger.info(f"Stream ended in {chat_id}")
    await play_next(chat_id)

# Main
async def main():
    logger.info("🚀 Starting Music Bot on Railway...")
    
    # Start web server
    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info(f"🌐 Web server started on port {PORT}")
    
    # Start Telegram clients
    await user_client.start()
    await bot.start()
    await call.start()
    
    me = await bot.get_me()
    logger.info(f"✅ Bot ready: @{me.username}")
    
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
