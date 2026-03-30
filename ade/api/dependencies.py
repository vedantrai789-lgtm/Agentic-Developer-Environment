"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ade.core.database import async_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for FastAPI Depends()."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
