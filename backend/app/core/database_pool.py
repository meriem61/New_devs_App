
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

from ..config import settings

logger = logging.getLogger(__name__)


class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None

    async def initialize(self):
        if self.engine is not None:
            return

        database_url = settings.database_url

        # SQLAlchemy needs the async PostgreSQL driver.
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace(
                "postgresql://",
                "postgresql+asyncpg://",
                1,
            )

        self.engine = create_async_engine(
            database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout,
            pool_pre_ping=True,
            pool_recycle=settings.database_pool_recycle,
            echo=False,
        )

        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Check that the database is actually reachable.
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

            logger.info("Database pool initialized successfully")

        except Exception:
            logger.exception("Database connection failed")
            await self.close()
            raise

    async def close(self):
        if self.engine is not None:
            await self.engine.dispose()

        self.engine = None
        self.session_factory = None

    def get_session(self):
        if self.session_factory is None:
            raise RuntimeError("Database pool is not initialized")

        return self.session_factory()


db_pool = DatabasePool()


async def get_db_session():
    async with db_pool.get_session() as session:
        yield session
