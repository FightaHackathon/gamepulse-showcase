"""Create the core GamePulse Fusion schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001_gamepulse_core"
down_revision = None
branch_labels = None
depends_on = None


def _source_columns() -> list[sa.Column]:
    return [
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_mode", sa.String(length=64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("steam_app_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("release_date", sa.String(length=128)),
        sa.Column("price_usd", sa.Float()),
        sa.Column("discount_pct", sa.Float()),
        sa.Column("required_age", sa.Integer()),
        sa.Column("owners_low", sa.BigInteger()),
        sa.Column("owners_high", sa.BigInteger()),
        sa.Column("peak_ccu", sa.BigInteger()),
        sa.Column("positive_reviews", sa.BigInteger()),
        sa.Column("negative_reviews", sa.BigInteger()),
        sa.Column("total_reviews", sa.BigInteger()),
        sa.Column("review_score", sa.Float()),
        sa.Column("recommendations", sa.BigInteger()),
        sa.Column("average_playtime_minutes", sa.Float()),
        sa.Column("median_playtime_minutes", sa.Float()),
        sa.Column("windows", sa.Boolean()),
        sa.Column("mac", sa.Boolean()),
        sa.Column("linux", sa.Boolean()),
        sa.Column("metacritic_score", sa.Float()),
        sa.Column("header_image_url", sa.Text()),
        sa.Column("website_url", sa.Text()),
        sa.Column("short_description", sa.Text()),
    )
    op.create_index("ix_games_name", "games", ["name"])

    op.create_table(
        "game_tags",
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("value", sa.String(length=255), primary_key=True),
    )
    op.create_table(
        "game_genres",
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("value", sa.String(length=255), primary_key=True),
    )
    op.create_table(
        "review_summaries",
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("review_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("recommended_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("not_recommended_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("review_score", sa.Float()),
        sa.Column("helpful_votes_total", sa.BigInteger()),
        sa.Column("funny_votes_total", sa.BigInteger()),
        sa.Column("average_word_count", sa.Float()),
        sa.Column("average_playtime_minutes", sa.Float()),
        sa.Column("latest_review_created_at_unix", sa.BigInteger()),
    )

    op.create_table(
        "steam_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric", sa.String(length=96), nullable=False),
        sa.Column("value_numeric", sa.Float()),
        sa.Column("value_text", sa.Text()),
        *_source_columns(),
        sa.UniqueConstraint("steam_app_id", "metric", "observed_at", "source_name", name="uq_steam_snapshot_metric"),
    )
    op.create_index("ix_steam_snapshots_steam_app_id", "steam_snapshots", ["steam_app_id"])
    op.create_index("ix_steam_snapshots_metric", "steam_snapshots", ["metric"])
    op.create_index("ix_steam_snapshots_observed_at", "steam_snapshots", ["observed_at"])

    op.create_table(
        "streaming_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE")),
        sa.Column("external_game_id", sa.String(length=255)),
        sa.Column("game_name", sa.String(length=512)),
        sa.Column("metric", sa.String(length=96), nullable=False),
        sa.Column("value_numeric", sa.Float()),
        sa.Column("value_text", sa.Text()),
        *_source_columns(),
        sa.UniqueConstraint("steam_app_id", "metric", "observed_at", "source_name", name="uq_streaming_snapshot_metric"),
    )
    op.create_index("ix_streaming_snapshots_steam_app_id", "streaming_snapshots", ["steam_app_id"])
    op.create_index("ix_streaming_snapshots_external_game_id", "streaming_snapshots", ["external_game_id"])
    op.create_index("ix_streaming_snapshots_metric", "streaming_snapshots", ["metric"])
    op.create_index("ix_streaming_snapshots_observed_at", "streaming_snapshots", ["observed_at"])

    op.create_table(
        "steamspy_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE"), nullable=False),
        sa.Column("owners_low", sa.BigInteger()),
        sa.Column("owners_high", sa.BigInteger()),
        *_source_columns(),
        sa.UniqueConstraint("steam_app_id", "observed_at", "source_name", name="uq_steamspy_snapshot"),
    )
    op.create_index("ix_steamspy_snapshots_steam_app_id", "steamspy_snapshots", ["steam_app_id"])
    op.create_index("ix_steamspy_snapshots_observed_at", "steamspy_snapshots", ["observed_at"])

    op.create_table(
        "trend_scores",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE"), nullable=False),
        sa.Column("audience", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False, server_default="GamePulse"),
        sa.Column("source_mode", sa.String(length=64), nullable=False, server_default="derived"),
        sa.Column("confidence", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("steam_app_id", "audience", "observed_at", name="uq_trend_score"),
    )
    op.create_index("ix_trend_scores_steam_app_id", "trend_scores", ["steam_app_id"])
    op.create_index("ix_trend_scores_observed_at", "trend_scores", ["observed_at"])

    op.create_table(
        "provider_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_name", sa.String(length=128), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_text", sa.Text()),
        sa.Column("metrics_written", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_provider_runs_provider_name", "provider_runs", ["provider_name"])
    op.create_index("ix_provider_runs_started_at", "provider_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_provider_runs_started_at", table_name="provider_runs")
    op.drop_index("ix_provider_runs_provider_name", table_name="provider_runs")
    op.drop_table("provider_runs")
    op.drop_index("ix_trend_scores_observed_at", table_name="trend_scores")
    op.drop_index("ix_trend_scores_steam_app_id", table_name="trend_scores")
    op.drop_table("trend_scores")
    op.drop_index("ix_steamspy_snapshots_observed_at", table_name="steamspy_snapshots")
    op.drop_index("ix_steamspy_snapshots_steam_app_id", table_name="steamspy_snapshots")
    op.drop_table("steamspy_snapshots")
    op.drop_index("ix_streaming_snapshots_observed_at", table_name="streaming_snapshots")
    op.drop_index("ix_streaming_snapshots_metric", table_name="streaming_snapshots")
    op.drop_index("ix_streaming_snapshots_external_game_id", table_name="streaming_snapshots")
    op.drop_index("ix_streaming_snapshots_steam_app_id", table_name="streaming_snapshots")
    op.drop_table("streaming_snapshots")
    op.drop_index("ix_steam_snapshots_observed_at", table_name="steam_snapshots")
    op.drop_index("ix_steam_snapshots_metric", table_name="steam_snapshots")
    op.drop_index("ix_steam_snapshots_steam_app_id", table_name="steam_snapshots")
    op.drop_table("steam_snapshots")
    op.drop_table("review_summaries")
    op.drop_table("game_genres")
    op.drop_table("game_tags")
    op.drop_index("ix_games_name", table_name="games")
    op.drop_table("games")
