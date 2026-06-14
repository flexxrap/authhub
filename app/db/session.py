from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# NullPool: each pytest-asyncio test runs in its own event loop, and a pooled
# asyncpg connection from a previous loop breaks ("attached to a different
# loop"). A fresh connection per checkout avoids that.
engine = create_async_engine(settings.database_url, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session
