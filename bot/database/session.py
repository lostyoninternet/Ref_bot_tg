from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from contextlib import asynccontextmanager

from bot.config import settings
from .models import Base


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Old tables removed when switching from raffles to grades (drop if exist)
_LEGACY_TABLES = ["raffle_winners", "raffles", "raffle_reminder_settings"]


async def init_db():
    """Initialize database: drop legacy raffle tables, create all current tables."""
    async with engine.begin() as conn:
        # Drop old raffle/reminder tables if present (migration from raffle to grades)
        for table in _LEGACY_TABLES:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Get async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
