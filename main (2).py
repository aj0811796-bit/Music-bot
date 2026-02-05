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
PORT = int(os.getenv("PORT", 8000))  # Railway provides PORT

# Validate
if not all([API_ID, API_HASH, BOT_TOKEN, SESSION_STRING]):
    logger.error("Missing environment variables!")
    sys.exit(1)

# Telegram imports
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ParseMode

# PyTgCalls imports - USING py-tgcalls==2.2.10
from py_tgcalls import PyTgCalls
from py_tgcalls.types import AudioPiped, AudioParameters
from py_tgcalls.exceptions import GroupCallNotFound, NoActiveGroupCall

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
            
            # Get best audio format
            formats = info.get('formats', [])
            audio_formats = [f for f in formats if f.get('acodec') != 'none']
            
            if audio_formats:
                # Sort by audio bitrate and get the best
                audio_formats.sort(key=lambda x: x.get('abr', 0) or 0, reverse=True)
                audio_url = audio_formats[0]['url']
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
        except Exception as e:
            logger.error(f"Join error: {e}")
            try:
                await call.change_stream(chat_id, audio)
            except:
                pass
        
        # Send playing message
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏸ Pause", callback_data="pause"),
                InlineKeyboardButton("⏭ Skip", callback_data="skip")
            ]
        ])
        
        await bot.send_message(
            chat_id,
            f"🎵 **Now Playing:** {song['title']}",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Play song error: {e}")
        await play_next(chat_id)

# Bot commands
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
        "/loop - Toggle loop\n"
        "/clear - Clear queue"
    )

@bot.on_message(filters.command("play") & filters.group)
async def play_cmd(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /play song_name")
        return
    
    query = " ".join(message.command[1:])
    chat_id = message.chat.id
    msg = await message.reply_text("🔍 Searching...")
    
    # Check if it's a direct URL
    if "youtube.com" in query or "youtu.be" in query:
        url = query
    else:
        url = await search_youtube(query)
        if not url:
            await msg.edit_text("❌ No results found!")
            return
    
    song = await get_stream_url(url)
    if not song or not song.get('url'):
        await msg.edit_text("❌ Could not get audio stream!")
        return
    
    if chat_id in now_playing:
        queue = get_queue(chat_id)
        queue.append(song)
        await msg.edit_text(f"✅ Added to queue: **{song['title']}**")
    else:
        await msg.edit_text("🎵 Playing...")
        await play_song(chat_id, song)

@bot.on_message(filters.command("splay") & filters.group)
async def splay_cmd(client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("❌ Usage: /splay query")
        return
    
    query = " ".join(message.command[1:])
    msg = await message.reply_text(f"🔍 Searching: {query}")
    
    try:
        search = VideosSearch(query, limit=5)
        results = search.result().get("result", [])
        
        if not results:
            await msg.edit_text("❌ No results found!")
            return
        
        buttons = []
        for i, result in enumerate(results):
            title = result['title'][:30] + "..." if len(result['title']) > 30 else result['title']
            duration = result.get('duration', 'N/A')
            buttons.append([
                InlineKeyboardButton(
                    f"{i+1}. {title} ({duration})",
                    callback_data=f"play_{result['id']}"
                )
            ])
        
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        await msg.edit_text(
            "🔍 **Search Results:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        await msg.edit_text("❌ Search failed!")

@bot.on_message(filters.command("queue"))
async def queue_cmd(client, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)
    
    if not queue and chat_id not in now_playing:
        await message.reply_text("🎶 Queue is empty!")
        return
    
    text = "📋 **Queue:**\n\n"
    
    if chat_id in now_playing:
        text += f"🎵 **Now Playing:** {now_playing[chat_id]['title']}\n\n"
    
    if queue:
        text += "**Up Next:**\n"
        for i, song in enumerate(queue[:10], 1):
            text += f"{i}. {song['title']}\n"
        if len(queue) > 10:
            text += f"\n... and {len(queue) - 10} more"
    
    await message.reply_text(text)

@bot.on_message(filters.command(["pause", "resume", "skip", "stop", "clear", "loop"]))
async def control_cmd(client, message: Message):
    chat_id = message.chat.id
    cmd = message.command[0]
    
    try:
        if cmd == "pause":
            await call.pause_stream(chat_id)
            await message.reply_text("⏸️ Playback paused")
            
        elif cmd == "resume":
            await call.resume_stream(chat_id)
            await message.reply_text("▶️ Playback resumed")
            
        elif cmd == "skip":
            if chat_id in now_playing:
                await message.reply_text("⏭️ Skipping...")
                await play_next(chat_id)
            else:
                await message.reply_text("❌ Nothing is playing!")
                
        elif cmd == "stop":
            await call.leave_group_call(chat_id)
            if chat_id in queues:
                queues[chat_id].clear()
            now_playing.pop(chat_id, None)
            await message.reply_text("🛑 Stopped playback and cleared queue")
            
        elif cmd == "clear":
            if chat_id in queues:
                queues[chat_id].clear()
            await message.reply_text("🗑️ Queue cleared!")
            
        elif cmd == "loop":
            loop_mode[chat_id] = not loop_mode.get(chat_id, False)
            status = "enabled" if loop_mode[chat_id] else "disabled"
            await message.reply_text(f"🔁 Loop {status}")
            
    except Exception as e:
        logger.error(f"Control error: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

@bot.on_callback_query()
async def callback_handler(client, callback: CallbackQuery):
    data = callback.data
    chat_id = callback.message.chat.id
    
    try:
        if data.startswith("play_"):
            video_id = data.split("_")[1]
            url = f"https://youtube.com/watch?v={video_id}"
            
            await callback.answer("🎵 Loading...")
            
            song = await get_stream_url(url)
            if song:
                if chat_id in now_playing:
                    queue = get_queue(chat_id)
                    queue.append(song)
                    await callback.message.edit_text(f"✅ Added to queue: **{song['title']}**")
                else:
                    await callback.message.delete()
                    await play_song(chat_id, song)
        
        elif data == "pause":
            await call.pause_stream(chat_id)
            await callback.answer("⏸️ Paused")
            
        elif data == "skip":
            if chat_id in now_playing:
                await callback.answer("⏭️ Skipping...")
                await play_next(chat_id)
            else:
                await callback.answer("❌ Nothing playing")
                
        elif data == "cancel":
            await callback.message.delete()
            await callback.answer("❌ Cancelled")
            
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await callback.answer("❌ Error occurred")

@call.on_stream_end()
async def stream_end(chat_id: int):
    logger.info(f"Stream ended in {chat_id}")
    
    # If loop mode is enabled, add current song back to queue
    if loop_mode.get(chat_id, False) and chat_id in now_playing:
        queue = get_queue(chat_id)
        queue.appendleft(now_playing[chat_id])
    
    await play_next(chat_id)

# Main function
async def main():
    logger.info("🚀 Starting Music Bot on Railway...")
    
    # Start web server for health checks
    web_thread = Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info(f"🌐 Web server started on port {PORT}")
    
    # Start Telegram clients
    logger.info("Starting Telegram clients...")
    await user_client.start()
    await bot.start()
    await call.start()
    
    me = await bot.get_me()
    logger.info(f"✅ Bot is ready: @{me.username}")
    
    logger.info("Bot is now running. Press Ctrl+C to stop.")
    
    # Keep the bot running
    await idle()
    
    # Cleanup
    await call.stop()
    await user_client.stop()
    await bot.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
