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
        
            # SQLite Auto-Migration: إضافة أي أعمدة جديدة تلقائياً
        try:
            from sqlalchemy import text
            res = await conn.execute(text("PRAGMA table_info(guild_configs);"))
            columns = [row[1] for row in res.fetchall()]
            new_cols = {
                "temp_voice_channel_id": "BIGINT",
                "leveling_channel_id": "BIGINT",
            }
            for col_name, col_type in new_cols.items():
                if col_name not in columns:
                    await conn.execute(text(f"ALTER TABLE guild_configs ADD COLUMN {col_name} {col_type};"))

            res_tickets = await conn.execute(text("PRAGMA table_info(support_tickets);"))
            ticket_cols = [row[1] for row in res_tickets.fetchall()]
            new_ticket_cols = {
                "evidence_type": "VARCHAR(20) DEFAULT 'NONE'",
                "evidence_url": "VARCHAR(500)",
                "evidence_status": "VARCHAR(20) DEFAULT 'NONE'",
                "evidence_analysis": "TEXT",
                "evidence_score": "INTEGER DEFAULT 0",
            }
            for col_name, col_type in new_ticket_cols.items():
                if col_name not in ticket_cols:
                    await conn.execute(text(f"ALTER TABLE support_tickets ADD COLUMN {col_name} {col_type};"))
        except Exception:
            pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
