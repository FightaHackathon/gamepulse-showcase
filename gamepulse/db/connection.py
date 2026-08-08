"""Small database connection boundary for web and maintenance entrypoints."""

from __future__ import annotations

import os

from sqlalchemy.engine import Engine

from .session import make_engine


def database_url(value: str | None = None) -> str:
    """Return the configured database URL without ever inventing a secret."""

    configured = value or os.getenv("DATABASE_URL")
    if not configured:
        raise RuntimeError("DATABASE_URL is required")
    return configured


def connect(value: str | None = None, *, managed_pooling: bool = False) -> Engine:
    """Create a pre-ping SQLAlchemy engine for a request or maintenance job."""

    return make_engine(database_url(value), managed_pooling=managed_pooling)
