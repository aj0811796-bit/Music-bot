import os
import asyncio
import logging
import sys
from collections import deque
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Get environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH") 
BOT_TOKEN = os.getenv("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING")

# Check environment variables
if not API_ID or not API_HASH or not BOT_TOKEN or not SESSION_STRING:
    logger.error("Missing environment variables!")
    logger.error("Set: API_ID, API_HASH, BOT_TOKEN, SESSION_STRING in Railway")
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    logger.error("API_ID must be a number!")
    sys.exit(1)

logger.info("✅ Environment variables loaded")

# Import Telegram - USE THESE EXACT IMPORTS
try:
    from pyrogram import Client, filters, idle
    from pyrogram.types import Message
    logger.info("✅ Pyrogram imported")
except ImportError as e:
    logger.error(f"Pyrogram import error: {e}")
    sys.exit(1)

# Import pytgcalls v3.0.0 - THESE ARE CORRECT
try:
    from pytgcalls import PyTgCalls
    from pytgcalls.types import AudioPiped
    logger.info("✅ pytgcalls imported")
except ImportError as e:
    logger.error(f"pytgcalls import error: {e}")
    logger.error("Make sure requirements.txt has: pytgcalls==3.0.0")
    sys.exit(1)

# Import YouTube
try:
    from youtubesearchpython import VideosSearch
    import yt_dlp
    logger.info("✅ YouTube libraries imported")
except ImportError as e:
    logger.error(f"YouTube import error: {e}")
    sys.exit(1)

# Import web server (optional)
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
        port = int(os.getenv("PORT", "8000"))
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    
    WEB_ENABLED = True
    logger.info("✅ Web server imported")
except ImportError:
    logger.warning("Web server libraries not found, skipping")
    WEB_ENABLED = False

# Bot storage
queues: Dict[int, deque] = {}
now_playing: Dict[int, Dict] = {}

# Initialize Telegram clients
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

# Initialize pytgcalls
call = PyTgCalls(user_client)

# Helper functions
async def search_youtube(query: str):
    """Search YouTube and return first result URL"""
    try:
        search = VideosSearch(query, limit=1)
        result = search.result()
        if result['result']:
            video_id = result['result'][0]['id']
            return f"https://youtube.com/watch?v={video_id}"
    except Exception as e:
        logger.error(f"Search error: {e}")
    return None

async def get_audio_url(youtube_url: str):
    """Get direct audio stream URL from YouTube"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'url': info['url']
            }
    except Exception as e:
        logger.error(f"Audio URL error: {e}")
    return None

async def play_song(chat_id: int, song: dict):
    """Play a song in voice chat"""
    try:
        now_playing[chat_id] = song
        
        # Create audio stream
        audio = AudioPiped(song['url'])
        
        # Join or change stream
        try:
            await call.join_group_call(chat_id, audio)
        except Exception:
            await call.change_stream(chat_id, audio)
        
        # Send playing message
        await bot.send_message(chat_id, f"🎵 **Now Playing:** {song['title']}")
        
    except Exception as e:
        logger.error(f"Play error in chat {chat_id}: {e}")
        now_playing.pop(chat_id, None)

async def play_next(chat_id: int):
    """Play next song in queue"""
    if chat_id in queues and queues[chat_id]:
        song = queues[chat_id].popleft()
        await play_song(chat_id, song)
    else:
        now_playing.pop(chat_id, None)
        await bot.send_message(chat_id, "✅ Queue finished!")

# Bot commands
@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Online!**\n\n"
        "**Commands:**\n"
        "/play [song] - Play music\n"
        "/skip - Skip current song\n"
        "/stop - Stop playback\n"
        "/queue - Show queue"
    )

@bot.on_message(filters.command("play") & filters.group)
async def play_command(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /play song_name")
        return
    
    query = " ".join(message.command[1:])
    chat_id = message.chat.id
    
    await message.reply_text("🔍 Searching...")
    
    # Search YouTube
    youtube_url = await search_youtube(query)
    if not youtube_url:
        await message.reply_text("❌ No results found!")
        return
    
    # Get audio URL
    song = await get_audio_url(youtube_url)
    if not song:
        await message.reply_text("❌ Error getting audio!")
        return
    
    # Initialize queue if needed
    if chat_id not in queues:
        queues[chat_id] = deque(maxlen=50)
    
    # Play or add to queue
    if chat_id in now_playing:
        queues[chat_id].append(song)
        await message.reply_text(f"✅ Added to queue: **{song['title']}**")
    else:
        await play_song(chat_id, song)

@bot.on_message(filters.command("skip") & filters.group)
async def skip_command(client, message: Message):
    chat_id = message.chat.id
    if chat_id in now_playing:
        await message.reply_text("⏭️ Skipping...")
        await play_next(chat_id)
    else:
        await message.reply_text("❌ Nothing is playing!")

@bot.on_message(filters.command("stop") & filters.group)
async def stop_command(client, message: Message):
    chat_id = message.chat.id
    try:
        await call.leave_group_call(chat_id)
        if chat_id in queues:
            queues[chat_id].clear()
        now_playing.pop(chat_id, None)
        await message.reply_text("🛑 Stopped")
    except Exception as e:
        logger.error(f"Stop error: {e}")
        await message.reply_text("❌ Error stopping!")

@bot.on_message(filters.command("queue") & filters.group)
async def queue_command(client, message: Message):
    chat_id = message.chat.id
    
    text = "📋 **Queue:**\n\n"
    
    # Current song
    if chat_id in now_playing:
        text += f"🎵 **Now Playing:** {now_playing[chat_id]['title']}\n\n"
    
    # Upcoming songs
    if chat_id in queues and queues[chat_id]:
        text += "**Up Next:**\n"
        for i, song in enumerate(list(queues[chat_id])[:10], 1):
            text += f"{i}. {song['title']}\n"
    else:
        text += "Queue is empty!"
    
    await message.reply_text(text)

# Handle stream end
@call.on_stream_end()
async def handle_stream_end(chat_id: int):
    logger.info(f"Stream ended in chat {chat_id}")
    await play_next(chat_id)

# Main function
async def main():
    logger.info("🚀 Starting Music Bot...")
    
    # Start web server if available
    if WEB_ENABLED:
        web_thread = Thread(target=run_web, daemon=True)
        web_thread.start()
        logger.info("🌐 Web server started")
    
    # Start Telegram clients
    await user_client.start()
    await bot.start()
    await call.start()
    
    me = await bot.get_me()
    logger.info(f"✅ Bot is ready: @{me.username}")
    
    # Keep bot running
    await idle()

# Run the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
