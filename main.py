#!/usr/bin/env python3
import asyncio
import sys
import os
from config import Config
from bot import TelegramBot

async def main():
    try:
        # Check configuration
        Config.check_config()
        
        # Initialize and start bot
        bot = TelegramBot()
        await bot.start()
        
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 8):
        print("Python 3.8 or higher is required!")
        sys.exit(1)
    
    # Run the bot
    asyncio.run(main())
