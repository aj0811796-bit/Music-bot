import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Railway automatically provides these from environment variables
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    SESSION_STRING = os.getenv("SESSION_STRING", "")
    
    # Railway-specific
    IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") == "production"
    PORT = int(os.getenv("PORT", 8080))
    
    @classmethod
    def check_config(cls):
        """Check if all required configs are set"""
        required = ["API_ID", "API_HASH", "BOT_TOKEN", "SESSION_STRING"]
        missing = []
        
        for var in required:
            value = getattr(cls, var)
            if not value:
                missing.append(var)
        
        if missing:
            error_msg = f"Missing required configs: {', '.join(missing)}\n"
            error_msg += "Please set these in Railway environment variables"
            raise ValueError(error_msg)
        
        print("✅ All configurations are set properly")
        
        if cls.IS_RAILWAY:
            print("🚂 Running on Railway")
        return True
