import os
import asyncio
import logging
import sys
from collections import deque
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
PORT = int(os.getenv("PORT", 8000))

# Validation
if not all([API_ID, API_HASH, BOT_TOKEN, SESSION_STRING]):
    logger.error("Missing environment variables!")
    sys.exit(1)

# Imports - FIXED VERSION
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

# Try different import styles for py-tgcalls
try:
    # Try py-tgcalls v2.x
    from py_tgcalls import PyTgCalls
    from py_tgcalls.types import AudioPiped, AudioParameters
    from py_tgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
    logger.info("Successfully imported py-tgcalls")
except ImportError:
    try:
        # Try alternative import path
        from py_tgcalls import PyTgCalls
        from py_tgcalls.types.input_stream import AudioPiped, AudioParameters
        from py_tgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall
        logger.info("Successfully imported py-tgcalls (alternative path)")
    except ImportError as e:
        logger.error(f"Failed to import py-tgcalls: {e}")
        sys.exit(1)

from youtubesearchpython import VideosSearch
import yt_dlp

# FastAPI for Railway health checks
try:
    from fastapi import FastAPI
    import uvicorn
    from threading import Thread
    
    app = FastAPI()
    
    @app.get("/")
    async def root():
        return {"status": "online"}
    
    @app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    def run_web():
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    
    WEB_SERVER = True
except ImportError:
    logger.warning("FastAPI not installed, web server disabled")
    WEB_SERVER = False

# Data storage
queues: Dict[int, deque] = {}
now_playing: Dict[int, Dict] = {}

# Initialize clients
bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_client = Client(
    "music_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

call = PyTgCalls(user_client)

# Helper functions
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
            return {
                'title': info.get('title', 'Unknown'),
                'url': info.get('url', ''),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail'),
            }
    except Exception as e:
        logger.error(f"Stream error: {e}")
    return None

async def play_next(chat_id: int):
    queue = get_queue(chat_id)
    if queue:
        song = queue.popleft()
        await play_song(chat_id, song)
    else:
        now_playing.pop(chat_id, None)
        await bot.send_message(chat_id, "✅ Queue finished!")

async def play_song(chat_id: int, song: Dict):
    try:
        now_playing[chat_id] = song
        
        # Create audio stream
        audio = AudioPiped(
            song['url'],
            AudioParameters.from_quality("high")
        )
        
        try:
            await call.join_group_call(chat_id, audio)
        except (GroupCallNotFound, NoActiveGroupCall):
            await bot.send_message(chat_id, "❌ Start voice chat first!")
            return
        except Exception:
            await call.change_stream(chat_id, audio)
        
        await bot.send_message(
            chat_id,
            f"🎵 **Now Playing:** {song['title']}"
        )
        
    except Exception as e:
        logger.error(f"Play error: {e}")
        await play_next(chat_id)

# Bot commands
@bot.on_message(filters.command("start"))
async def start_cmd(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Online!**\n\n"
        "**Commands:**\n"
        "/play [song] - Play music\n"
        "/skip - Skip current song\n"
        "/stop - Stop playback\n"
        "/queue - Show queue\n"
        "/pause - Pause\n"
        "/resume - Resume"
    )

@bot.on_message(filters.command("play") & filters.group)
async def play_cmd(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /play song_name")
        return
    
    query = " ".join(message.command[1:])
    chat_id = message.chat.id
    
    msg = await message.reply_text("🔍 Searching...")
    
    # Get YouTube URL
    if "youtube.com" in query or "youtu.be" in query:
        url = query
    else:
        url = await search_youtube(query)
        if not url:
            await msg.edit_text("❌ No results!")
            return
    
    # Get stream URL
    song = await get_stream_url(url)
    if not song:
        await msg.edit_text("❌ Error getting audio!")
        return
    
    # Play or add to queue
    if chat_id in now_playing:
        queue = get_queue(chat_id)
        queue.append(song)
        await msg.edit_text(f"✅ Added to queue: {song['title']}")
    else:
        await msg.edit_text("🎵 Playing...")
        await play_song(chat_id, song)

@bot.on_message(filters.command(["skip", "stop"]))
async def control_cmd(client, message: Message):
    chat_id = message.chat.id
    cmd = message.command[0]
    
    if cmd == "skip":
        if chat_id in now_playing:
            await message.reply_text("⏭️ Skipping...")
            await play_next(chat_id)
        else:
            await message.reply_text("❌ Nothing playing!")
    elif cmd == "stop":
        try:
            await call.leave_group_call(chat_id)
            queues.pop(chat_id, None)
            now_playing.pop(chat_id, None)
            await message.reply_text("🛑 Stopped")
        except:
            await message.reply_text("❌ Error!")

@bot.on_message(filters.command("queue"))
async def queue_cmd(client, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    
    if not queue and chat_id not in now_playing:
        await message.reply_text("🎶 Queue empty!")
        return
    
    text = "📋 **Queue:**\n\n"
    if chat_id in now_playing:
        text += f"🎵 **Playing:** {now_playing[chat_id]['title']}\n\n"
    
    if queue:
        for i, song in enumerate(queue[:10], 1):
            text += f"{i}. {song['title']}\n"
    
    await message.reply_text(text)

@call.on_stream_end()
async def stream_end(chat_id: int):
    logger.info(f"Stream ended in {chat_id}")
    await play_next(chat_id)

# Main function
async def main():
    logger.info("🚀 Starting Music Bot...")
    
    # Start web server if available
    if WEB_SERVER:
        web_thread = Thread(target=run_web, daemon=True)
        web_thread.start()
        logger.info(f"🌐 Web server on port {PORT}")
    
    # Start Telegram clients
    await user_client.start()
    await bot.start()
    await call.start()
    
    me = await bot.get_me()
    logger.info(f"✅ Bot ready: @{me.username}")
    
    # Keep running
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
