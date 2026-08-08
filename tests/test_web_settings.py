import pytest
from pydantic import ValidationError

from gamepulse.web_api.settings import WebSettings


def test_web_settings_do_not_model_user_steam_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    settings = WebSettings()
    assert not hasattr(settings, "steam_web_api_key")


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        WebSettings()
