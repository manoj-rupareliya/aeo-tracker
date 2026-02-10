"""
Database connection and session management
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models import Base

# Lazy initialization for serverless environments
_engine = None
_async_session_maker = None
_sync_engine = None
_sync_session_maker = None


def _get_database_url() -> str:
    """Get and convert database URL for async"""
    settings = get_settings()
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def _is_serverless() -> bool:
    """Check if running in serverless environment"""
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _get_engine():
    """Lazy engine initialization"""
    global _engine
    if _engine is None:
        settings = get_settings()

        engine_kwargs = {
            "echo": settings.DEBUG,
            "pool_pre_ping": True,
        }

        if _is_serverless():
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = settings.DATABASE_POOL_SIZE
            engine_kwargs["max_overflow"] = settings.DATABASE_MAX_OVERFLOW

        _engine = create_async_engine(
            _get_database_url(),
            **engine_kwargs
        )
    return _engine


def _get_session_maker():
    """Lazy session maker initialization"""
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    session_maker = _get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session (for use outside of FastAPI)"""
    session_maker = _get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


# For Celery workers (sync context) - also lazy loaded
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def _get_sync_engine():
    """Lazy sync engine initialization"""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        _sync_engine = create_engine(
            settings.DATABASE_URL,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_pre_ping=True,
        )
    return _sync_engine


def _get_sync_session_maker():
    """Lazy sync session maker initialization"""
    global _sync_session_maker
    if _sync_session_maker is None:
        _sync_session_maker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_get_sync_engine(),
        )
    return _sync_session_maker


def get_sync_db() -> Session:
    """Get synchronous database session for Celery workers"""
    session_maker = _get_sync_session_maker()
    db = session_maker()
    try:
        return db
    except Exception:
        db.rollback()
        raise
