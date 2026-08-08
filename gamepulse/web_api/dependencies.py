from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from gamepulse.db.session import make_engine
from gamepulse.web_api.settings import WebSettings


def get_db_session() -> Iterator[Session]:
    """Yield one request-scoped database session.

    Cached read routes depend on this boundary rather than creating provider
    clients. Visitor requests therefore never trigger external market fetches.
    """

    settings = WebSettings()
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
