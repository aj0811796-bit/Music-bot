import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped
from youtubesearchpython import VideosSearch
import yt_dlp

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get environment variables from Railway
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Validate
if not all([API_ID, API_HASH, BOT_TOKEN]):
    logger.error("❌ Missing environment variables!")
    logger.error("Set API_ID, API_HASH, BOT_TOKEN in Railway Variables")
    exit(1)

# Initialize bot
bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Initialize pytgcalls
call = PyTgCalls(bot)

# Store queues
queues = {}
current_playing = {}

# Search YouTube
async def search_youtube(query):
    try:
        search = VideosSearch(query, limit=1)
        result = search.result()
        if result['result']:
            return f"https://youtube.com/watch?v={result['result'][0]['id']}"
    except Exception as e:
        logger.error(f"Search error: {e}")
    return None

# Get audio URL
async def get_audio_url(youtube_url):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
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

# Play song
async def play_song(chat_id, song):
    try:
        current_playing[chat_id] = song
        await call.join_group_call(
            chat_id,
            AudioPiped(song['url'])
        )
        await bot.send_message(chat_id, f"🎵 **Now Playing:** {song['title']}")
    except Exception as e:
        logger.error(f"Play error: {e}")
        current_playing.pop(chat_id, None)

# Bot commands
@bot.on_message(filters.command("start"))
async def start_command(client, message: Message):
    await message.reply_text(
        "🎵 **Music Bot Online!**\n\n"
        "**Commands:**\n"
        "/play [song] - Play music\n"
        "/skip - Skip song\n"
        "/stop - Stop music\n"
        "/queue - Show queue\n\n"
        "Made for Railway 🚄"
    )

@bot.on_message(filters.command("play"))
async def play_command(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /play song_name")
        return
    
    query = " ".join(message.command[1:])
    chat_id = message.chat.id
    
    # Send searching message
    msg = await message.reply_text("🔍 Searching...")
    
    # Search YouTube
    youtube_url = await search_youtube(query)
    if not youtube_url:
        await msg.edit_text("❌ No results found!")
        return
    
    # Get audio stream
    song = await get_audio_url(youtube_url)
    if not song:
        await msg.edit_text("❌ Error getting audio!")
        return
    
    # Initialize queue if needed
    if chat_id not in queues:
        queues[chat_id] = []
    
    # Play or add to queue
    if chat_id in current_playing:
        queues[chat_id].append(song)
        await msg.edit_text(f"✅ Added to queue: **{song['title']}**")
    else:
        await msg.edit_text("🎵 Playing...")
        await play_song(chat_id, song)

@bot.on_message(filters.command("skip"))
async def skip_command(client, message: Message):
    chat_id = message.chat.id
    if chat_id in current_playing:
        await message.reply_text("⏭️ Skipping...")
        # Leave call
        try:
            await call.leave_group_call(chat_id)
        except:
            pass
        # Play next if exists in queue
        if chat_id in queues and queues[chat_id]:
            next_song = queues[chat_id].pop(0)
            await play_song(chat_id, next_song)
        else:
            current_playing.pop(chat_id, None)
    else:
        await message.reply_text("❌ Nothing is playing!")

@bot.on_message(filters.command("stop"))
async def stop_command(client, message: Message):
    chat_id = message.chat.id
    try:
        await call.leave_group_call(chat_id)
        if chat_id in queues:
            queues[chat_id].clear()
        current_playing.pop(chat_id, None)
        await message.reply_text("🛑 Stopped")
    except:
        await message.reply_text("❌ Error stopping!")

@bot.on_message(filters.command("queue"))
async def queue_command(client, message: Message):
    chat_id = message.chat.id
    
    text = "📋 **Queue:**\n\n"
    
    # Current song
    if chat_id in current_playing:
        text += f"🎵 **Now Playing:** {current_playing[chat_id]['title']}\n\n"
    
    # Queue
    if chat_id in queues and queues[chat_id]:
        text += "**Up Next:**\n"
        for i, song in enumerate(queues[chat_id][:10], 1):
            text += f"{i}. {song['title']}\n"
        if len(queues[chat_id]) > 10:
            text += f"\n... and {len(queues[chat_id]) - 10} more"
    else:
        text += "Queue is empty!"
    
    await message.reply_text(text)

# Stream end handler
@call.on_stream_end()
async def stream_end_handler(chat_id: int):
    logger.info(f"Stream ended in {chat_id}")
    # Play next song if available
    if chat_id in queues and queues[chat_id]:
        next_song = queues[chat_id].pop(0)
        await play_song(chat_id, next_song)
    else:
        current_playing.pop(chat_id, None)

# Start the bot
async def main():
    logger.info("🚀 Starting Music Bot on Railway...")
    await call.start()
    await bot.start()
    
    me = await bot.get_me()
    logger.info(f"✅ Bot is ready: @{me.username}")
    
    # Keep running
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
