import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Credentials
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    SESSION_STRING = os.getenv("SESSION_STRING", "")
    
    # Bot Settings
    BOT_USERNAME = os.getenv("BOT_USERNAME", "")
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    
    # Database (Optional)
    MONGO_URL = os.getenv("MONGO_URL", "")
    REDIS_URL = os.getenv("REDIS_URL", "")
    
    # Music Settings
    MAX_PLAYLIST_SIZE = int(os.getenv("MAX_PLAYLIST_SIZE", 50))
    MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", 100))
    DURATION_LIMIT = int(os.getenv("DURATION_LIMIT", 3600))
    
    @classmethod
    def check_config(cls):
        """Check if all required configs are set"""
        required = ["API_ID", "API_HASH", "BOT_TOKEN", "SESSION_STRING"]
        missing = [var for var in required if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required configs: {', '.join(missing)}")
        
        print("✅ All configurations are set properly")
        return True