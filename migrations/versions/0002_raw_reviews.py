"""Retain raw review records from the recovered catalog."""

from alembic import op
import sqlalchemy as sa


revision = "0002_raw_reviews"
down_revision = "0001_gamepulse_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("review_id", sa.String(length=255), primary_key=True),
        sa.Column("steam_app_id", sa.Integer(), sa.ForeignKey("games.steam_app_id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer()),
        sa.Column("recommended", sa.Boolean()),
        sa.Column("helpful_votes", sa.BigInteger()),
        sa.Column("funny_votes", sa.BigInteger()),
        sa.Column("created_at_unix", sa.BigInteger()),
        sa.Column("author_playtime_minutes", sa.BigInteger()),
        sa.Column("source_game_name", sa.String(length=512)),
        sa.Column("source_price", sa.Float()),
        sa.Column("source_release_date", sa.String(length=128)),
        sa.Column("source_name", sa.String(length=128), nullable=False, server_default="GamePulse prototype SQLite"),
        sa.Column("source_mode", sa.String(length=64), nullable=False, server_default="historical_import"),
        sa.Column("source_url", sa.Text()),
    )
    op.create_index("ix_reviews_steam_app_id", "reviews", ["steam_app_id"])
    op.create_index("ix_reviews_created_at_unix", "reviews", ["created_at_unix"])


def downgrade() -> None:
    op.drop_index("ix_reviews_created_at_unix", table_name="reviews")
    op.drop_index("ix_reviews_steam_app_id", table_name="reviews")
    op.drop_table("reviews")
