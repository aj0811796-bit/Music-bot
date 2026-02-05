import os
import asyncio
import logging
from typing import Dict
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get env vars
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

if not all([API_ID, API_HASH, BOT_TOKEN, SESSION_STRING]):
    logger.error("Missing env vars!")
    exit(1)

# Imports for pytgcalls
try:
    from pyrogram import Client, filters, idle
    from pyrogram.types import Message
    logger.info("✅ Pyrogram imported")
    
    from pytgcalls import PyTgCalls
    from pytgcalls.types import AudioPiped
    logger.info("✅ py-tgcalls imported")
    
    from youtubesearchpython import VideosSearch
    import yt_dlp
    logger.info("✅ YouTube libraries imported")
    
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    exit(1)

# Initialize clients
bot = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_client = Client("user", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
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
    except:
        pass
    return None

# Get audio URL
async def get_audio_url(url: str):
    try:
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {'title': info.get('title', 'Unknown'), 'url': info['url']}
    except:
        return None

# Bot commands
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply("🎵 Music Bot Online! Use /play song")

@bot.on_message(filters.command("play"))
async def play(client, message: Message):
    if len(message.command) < 2:
        await message.reply("Usage: /play song_name")
        return
    
    query = " ".join(message.command[1:])
    chat_id = message.chat.id
    
    msg = await message.reply("🔍 Searching...")
    
    youtube_url = await search_youtube(query)
    if not youtube_url:
        await msg.edit("❌ No results!")
        return
    
    song = await get_audio_url(youtube_url)
    if not song:
        await msg.edit("❌ Error!")
        return
    
    if chat_id not in queues:
        queues[chat_id] = deque()
    
    if await call.get_active_call(chat_id):
        queues[chat_id].append(song)
        await msg.edit(f"✅ Added: {song['title']}")
    else:
        await msg.edit("🎵 Playing...")
        try:
            await call.join_group_call(chat_id, AudioPiped(song['url']))
            await message.reply(f"🎵 Now Playing: {song['title']}")
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")

@bot.on_message(filters.command("skip"))
async def skip(client, message: Message):
    chat_id = message.chat.id
    await message.reply("⏭️ Skipping...")
    await call.leave_group_call(chat_id)

@call.on_stream_end()
async def stream_end(chat_id: int):
    logger.info(f"Stream ended: {chat_id}")

# Main
async def main():
    await user_client.start()
    await bot.start()
    await call.start()
    
    me = await bot.get_me()
    logger.info(f"✅ Bot ready: @{me.username}")
    
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
