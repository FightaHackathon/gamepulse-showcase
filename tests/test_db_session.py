from gamepulse.db.session import _sqlalchemy_database_url


def test_make_engine_uses_installed_psycopg_driver_for_plain_postgres_urls():
    assert _sqlalchemy_database_url("postgresql://user:password@example.test/gamepulse") == (
        "postgresql+psycopg://user:password@example.test/gamepulse"
    )
