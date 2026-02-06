from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped, AudioVideoPiped
from pyrogram.types import Message
import asyncio
from typing import Dict, List
from collections import deque

class MusicPlayer:
    def __init__(self, client):
        self.client = client
        self.calls = PyTgCalls(client)
        self.queues: Dict[int, deque] = {}
        self.current: Dict[int, Dict] = {}
        self.loop: Dict[int, bool] = {}
        
    async def start(self):
        """Start the PyTgCalls client"""
        await self.calls.start()
        print("✅ PyTgCalls started successfully")
    
    async def join_vc(self, chat_id: int, message: Message):
        """Join voice chat"""
        try:
            await self.calls.join_group_call(
                chat_id,
                AudioPiped(
                    "http://docs.evostream.com/sample_content/assets/sintel1m720p.mp4",
                )
            )
            await message.reply("✅ Joined voice chat!")
            return True
        except Exception as e:
            await message.reply(f"❌ Failed to join VC: {str(e)}")
            return False
    
    async def play(self, chat_id: int, audio_url: str, title: str = "Unknown"):
        """Play audio in voice chat"""
        try:
            await self.calls.join_group_call(
                chat_id,
                AudioPiped(
                    audio_url,
                ),
                stream_type="music"
            )
            self.current[chat_id] = {'url': audio_url, 'title': title}
            return True
        except Exception as e:
            print(f"Play error: {e}")
            return False
    
    async def stop(self, chat_id: int):
        """Stop playback"""
        try:
            await self.calls.leave_group_call(chat_id)
            if chat_id in self.current:
                del self.current[chat_id]
            return True
        except:
            return False
    
    async def pause(self, chat_id: int):
        """Pause playback"""
        try:
            await self.calls.pause_stream(chat_id)
            return True
        except:
            return False
    
    async def resume(self, chat_id: int):
        """Resume playback"""
        try:
            await self.calls.resume_stream(chat_id)
            return True
        except:
            return False
    
    async def skip(self, chat_id: int):
        """Skip current track"""
        # Implementation for skipping to next in queue
        pass
    
    def add_to_queue(self, chat_id: int, track: Dict):
        """Add track to queue"""
        if chat_id not in self.queues:
            self.queues[chat_id] = deque(maxlen=100)
        self.queues[chat_id].append(track)
    
    def get_queue(self, chat_id: int) -> List[Dict]:
        """Get current queue"""
        return list(self.queues.get(chat_id, []))
    
    def clear_queue(self, chat_id: int):
        """Clear queue"""
        if chat_id in self.queues:
            self.queues[chat_id].clear()
