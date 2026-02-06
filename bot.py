from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import Config
from player import MusicPlayer
from utils import YouTube, format_duration
import asyncio

# FIXED IMPORT - Add these 2 lines:
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types import AudioPiped, AudioQuality

class TelegramBot:
    def __init__(self):
        self.app = Client(
            "music_bot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="plugins")
        )
        self.player = MusicPlayer(self.app)
        
        # Register handlers
        self.register_handlers()
    class TelegramBot:
    def __init__(self):
        self.app = Client(
            "music_bot",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            plugins=dict(root="plugins"),
            sleep_threshold=30  # ADD THIS LINE
        )
        self.player = MusicPlayer(self.app)
        
        # Register handlers
        self.register_handlers()
    
    # Add this new method:
    async def keep_alive(self):
        """Send periodic updates to prevent timeouts"""
        import time
        while True:
            try:
                me = await self.app.get_me()
                logger.info(f"🟢 Bot alive: @{me.username}")
            except:
                logger.warning("Keep-alive check failed")
            await asyncio.sleep(300)  # Check every 5 minutes
    def register_handlers(self):
        @self.app.on_message(filters.command("start") & filters.private)
        async def start_command(client, message: Message):
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Commands", callback_data="help")],
                [InlineKeyboardButton("📢 Support", url="https://t.me/yourchannel")],
                [InlineKeyboardButton("💻 Source", url="https://github.com/yourusername/telegram-music-bot")]
            ])
            
            await message.reply(
                f"**🎵 Music Bot**\n\n"
                f"Hello {message.from_user.mention}!\n"
                f"I can play music in voice chats.\n\n"
                f"**Features:**\n"
                f"• High quality audio\n"
                f"• YouTube/SoundCloud support\n"
                f"• Queue system\n"
                f"• 24/7 playback\n",
                reply_markup=keyboard
            )
        
        @self.app.on_message(filters.command("play") & filters.group)
        async def play_command(client, message: Message):
            if len(message.command) < 2:
                await message.reply("**Usage:** `/play song name or URL`")
                return
            
            query = " ".join(message.command[1:])
            
            # Check if user is in voice chat
            if not message.from_user:
                await message.reply("You need to be in a voice chat first!")
                return
            
            # Search for song
            msg = await message.reply("🔍 Searching...")
            
            # Check if query is URL
            if "youtube.com" in query or "youtu.be" in query:
                audio_info = await YouTube.get_audio_url(query)
            else:
                # Search YouTube
                results = await YouTube.search(query, limit=1)
                if not results:
                    await msg.edit("❌ No results found!")
                    return
                audio_info = await YouTube.get_audio_url(results[0]['url'])
            
            if not audio_info:
                await msg.edit("❌ Could not get audio!")
                return
            
            # Join VC if not already joined
            chat_id = message.chat.id
            try:
                await self.player.play(chat_id, audio_info['url'], audio_info['title'])
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏸ Pause", callback_data="pause"),
                     InlineKeyboardButton("⏭ Skip", callback_data="skip")],
                    [InlineKeyboardButton("📋 Queue", callback_data="queue")]
                ])
                
                await msg.edit(
                    f"**🎶 Now Playing**\n\n"
                    f"**Title:** {audio_info['title']}\n"
                    f"**Duration:** {format_duration(audio_info.get('duration', 0))}\n\n"
                    f"Requested by: {message.from_user.mention}",
                    reply_markup=keyboard
                )
            except Exception as e:
                await msg.edit(f"❌ Error: {str(e)}")
        
        @self.app.on_message(filters.command("pause") & filters.group)
        async def pause_command(client, message: Message):
            chat_id = message.chat.id
            if await self.player.pause(chat_id):
                await message.reply("⏸ Music paused")
            else:
                await message.reply("❌ Not playing anything")
        
        @self.app.on_message(filters.command("resume") & filters.group)
        async def resume_command(client, message: Message):
            chat_id = message.chat.id
            if await self.player.resume(chat_id):
                await message.reply("▶ Music resumed")
            else:
                await message.reply("❌ Nothing to resume")
        
        @self.app.on_message(filters.command("stop") & filters.group)
        async def stop_command(client, message: Message):
            chat_id = message.chat.id
            if await self.player.stop(chat_id):
                await message.reply("⏹ Music stopped")
                self.player.clear_queue(chat_id)
            else:
                await message.reply("❌ Not in voice chat")
        
        @self.app.on_message(filters.command("queue") & filters.group)
        async def queue_command(client, message: Message):
            chat_id = message.chat.id
            queue = self.player.get_queue(chat_id)
            
            if not queue:
                await message.reply("📭 Queue is empty!")
                return
            
            text = "**📋 Current Queue:**\n\n"
            for i, track in enumerate(queue[:10], 1):
                text += f"{i}. {track.get('title', 'Unknown')}\n"
            
            if len(queue) > 10:
                text += f"\n... and {len(queue) - 10} more tracks"
            
            await message.reply(text)
        
        @self.app.on_message(filters.command("help"))
        async def help_command(client, message: Message):
            help_text = """
**🎵 Music Bot Commands:**

**Playback:**
/play [song/url] - Play music
/stop - Stop playback
/pause - Pause music
/resume - Resume music
/skip - Skip current song

**Queue:**
/queue - Show queue
/clear - Clear queue

**Info:**
/now - Current playing
/lyrics [song] - Get lyrics
/search [query] - Search songs

**Admin:**
/join - Join voice chat
/leave - Leave voice chat
"""
            await message.reply(help_text)
    
    async def start(self):
        """Start the bot"""
        print("Starting bot...")
        await self.player.start()
        await self.app.start()
        print("✅ Bot started successfully!")
        
        # Get bot info
        me = await self.app.get_me()
        print(f"Bot: @{me.username}")
        print("Waiting for messages...")
        
        await self.app.idle()
    
    async def stop(self):
        """Stop the bot"""
        await self.app.stop()
