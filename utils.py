import yt_dlp
import os
import asyncio
from typing import Dict, List, Optional, Tuple
import aiohttp
import re

class YouTube:
    @staticmethod
    async def search(query: str, limit: int = 10) -> List[Dict]:
        """Search YouTube for videos"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'format': 'bestaudio/best',
            'noplaylist': True,
            'extract_flat': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                return info.get('entries', [])
        except Exception as e:
            print(f"Search error: {e}")
            return []

    @staticmethod
    async def get_audio_url(url: str) -> Optional[str]:
        """Extract audio URL from YouTube/SoundCloud"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                return {
                    'url': info['url'],
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                }
        except Exception as e:
            print(f"Audio extraction error: {e}")
            return None

def format_duration(seconds: int) -> str:
    """Format seconds to HH:MM:SS or MM:SS"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def clean_filename(filename: str) -> str:
    """Clean filename for safe usage"""
    return re.sub(r'[<>:"/\\|?*]', '', filename)
