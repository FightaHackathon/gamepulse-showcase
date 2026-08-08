from pydantic_settings import BaseSettings, SettingsConfigDict


class WebSettings(BaseSettings):
    """Server-owned GamePulse web configuration.

    Visitor-provided Steam Web API keys are request-scoped credentials and are
    intentionally not represented here so they cannot be persisted by normal
    server configuration code.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    cron_secret: str | None = None
    mistral_api_key: str | None = None
    app_env: str = "development"
    provider_timeout_seconds: float = 15.0
    snapshot_stale_hours: int = 48
