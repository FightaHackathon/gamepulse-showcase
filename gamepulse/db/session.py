from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


def _sqlalchemy_database_url(database_url: str) -> str:
    """Use the psycopg v3 driver installed by the application.

    Neon commonly supplies a plain ``postgresql://`` URL. SQLAlchemy's
    default PostgreSQL driver is psycopg2, while this project intentionally
    depends on psycopg v3 via ``psycopg[binary]``.
    """

    for prefix in ("postgresql://", "postgres://"):
        if database_url.startswith(prefix):
            return f"postgresql+psycopg://{database_url[len(prefix):]}"
    return database_url


def make_engine(database_url: str, *, managed_pooling: bool = False) -> Engine:
    kwargs: dict = {"pool_pre_ping": True}
    if not managed_pooling:
        kwargs["poolclass"] = NullPool
    return create_engine(_sqlalchemy_database_url(database_url), **kwargs)


def make_session_factory(database_url: str, *, managed_pooling: bool = False) -> sessionmaker[Session]:
    return sessionmaker(bind=make_engine(database_url, managed_pooling=managed_pooling), expire_on_commit=False)


@contextmanager
def session_scope(database_url: str, *, managed_pooling: bool = False) -> Iterator[Session]:
    factory = make_session_factory(database_url, managed_pooling=managed_pooling)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
