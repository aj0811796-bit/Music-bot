# 🎵 Telegram Music Bot

A feature-rich Telegram bot for playing music in voice chats.

## Features
- 🎶 High quality audio playback
- 📋 Queue system
- 🔍 YouTube/SoundCloud support
- ⏯️ Playback controls (pause/resume/skip)
- 👥 Multi-group support
- 🌐 24/7 online (when hosted)

## Deployment

### 1. Local Setup
```bash
# Clone repository
git clone https://github.com/yourusername/telegram-music-bot.git
cd telegram-music-bot

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Generate session string
python generate_session.py

# Run bot
python main.py
