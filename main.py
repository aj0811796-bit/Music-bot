#!/usr/bin/env python3
import asyncio
import sys
import os
import logging
from config import Config
from bot import TelegramBot

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("🚀 Starting Telegram Music Bot...")
        
        # Check configuration
        Config.check_config()
        
        # Initialize and start bot
        bot = TelegramBot()
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Railway sets PORT environment variable
    port = os.environ.get("PORT")
    if port:
        logger.info(f"Railway detected. PORT: {port}")
    
    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("Python 3.8 or higher is required!")
        sys.exit(1)
    
    # Run the bot
    asyncio.run(main())
