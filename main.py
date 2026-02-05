import os
import asyncio
import logging
from collections import deque
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

if not all([API_ID, API_HASH, BOT_TOKEN, SESSION_STRING]):
    logger.error("Missing environment variables!")
    exit(1)

# Imports from GitHub packages
try:
    # Pyrogram from GitHub
    from pyrogram import Client, filters, idle
    from pyrogram.types import Message
    logger.info("✅ Pyrogram imported from GitHub")
    
    # PyTgCalls from GitHub
    from pytgcalls import PyTgCalls
    from pytgcalls.types import AudioPiped
    logger.info("✅ PyTgCalls imported from GitHub")
    
    # YouTube libraries
    from youtubesearchpython import VideosSearch
    import yt_dlp
    logger.info("✅ YouTube libraries imported")
    
except ImportError as e:
    logger.error(f"❌ Import error: {e}")
    exit(1)

# Initialize clients
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_client = Client("music_user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
call = PyTgCalls(user_client)

# Storage
queues: Dict[int, deque] = {}

# Search YouTube
async def search_youtube(query: str):
    try:
        search = VideosSearch(query, limit=1)
        result = search.result()
        if result['result']:
            return f"https://youtube.com/watch?v={result['result'][0]['id']}"
    except Exception as e:
        logger.error(f"Search error: {e}")
    return None

# Get audio stream
async def get_audio_url(youtube_url: str):
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
        logger.error(f"Audio error: {e}")
    return None

# Bot commands
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Online!**\n\n"
        "**Commands:**\n"
        "/play [song] - Play music\n"
        "/skip - Skip song\n"
        "/stop - Stop music"
    )

@bot.on_message(filters.command("play"))
async def play(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /play song_name")
        return
    
    query = " ".join(message.command[1:])
    chat_id = message.chat.id
    
    msg = await message.reply_text("🔍 Searching...")
    
    # Search YouTube
    youtube_url = await search_youtube(query)
    if not youtube_url:
        await msg.edit_text("❌ No results found!")
        return
    
    # Get audio
    song = await get_audio_url(youtube_url)
    if not song:
        await msg.edit_text("❌ Error getting audio!")
        return
    
    # Initialize queue
    if chat_id not in queues:
        queues[chat_id] = deque(maxlen=50)
    
    # Play or add to queue
    try:
        await call.join_group_call(chat_id, AudioPiped(song['url']))
        await msg.edit_text(f"🎵 **Now Playing:** {song['title']}")
    except Exception as e:
        logger.error(f"Play error: {e}")
        queues[chat_id].append(song)
        await msg.edit_text(f"✅ Added to queue: {song['title']}")

@bot.on_message(filters.command(["skip", "stop"]))
async def control(client, message: Message):
    chat_id = message.chat.id
    cmd = message.command[0]
    
    try:
        await call.leave_group_call(chat_id)
        if cmd == "stop" and chat_id in queues:
            queues[chat_id].clear()
        await message.reply_text("✅ Done")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

# Stream end handler
@call.on_stream_end()
async def stream_end_handler(chat_id: int):
    logger.info(f"Stream ended in {chat_id}")
    if chat_id in queues and queues[chat_id]:
        next_song = queues[chat_id].popleft()
        try:
            await call.join_group_call(chat_id, AudioPiped(next_song['url']))
        except:
            pass

# Main function
async def main():
    logger.info("🚀 Starting Music Bot...")
    
    # Start clients
    await user_client.start()
    await bot.start()
    await call.start()
    
    me = await bot.get_me()
    logger.info(f"✅ Bot ready: @{me.username}")
    
    # Keep running
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
