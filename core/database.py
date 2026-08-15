from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import Config

engine = create_async_engine(Config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def init_db():
    import core.models  # Ensures all models are registered with Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # SQLite Auto-Migration: فحص الأعمدة المضافة حديثاً وإضافتها تلقائياً إن لم تكن موجودة
        try:
            from sqlalchemy import text
            res = await conn.execute(text("PRAGMA table_info(guild_configs);"))
            columns = [row[1] for row in res.fetchall()]
            if "temp_voice_channel_id" not in columns:
                await conn.execute(text("ALTER TABLE guild_configs ADD COLUMN temp_voice_channel_id BIGINT;"))
        except Exception:
            pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
