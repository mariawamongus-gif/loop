import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "").strip().strip('"').strip("'")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///neon.db").strip()
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0").strip()

    
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    
    HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")
    HUGGINGFACE_MODEL: str = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")


    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.80
    EMBED_COLOR: int = 0x1E1E2E  # Dark sleek industrial color
    EMBED_COLOR_ERROR: int = 0xFF5555
    EMBED_COLOR_SUCCESS: int = 0x50FA7B
    EMBED_COLOR_WARNING: int = 0xFFB86C
    EMBED_COLOR_CRITICAL: int = 0xFF0000
