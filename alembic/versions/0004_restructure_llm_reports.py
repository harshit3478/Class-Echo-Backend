"""restructure llm_reports: add score_breakdown and quantitative_metrics, drop strengths/improvements

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-20

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("llm_reports", sa.Column("score_breakdown", JSONB(), nullable=True))
    op.add_column("llm_reports", sa.Column("quantitative_metrics", JSONB(), nullable=True))
    op.drop_column("llm_reports", "strengths")
    op.drop_column("llm_reports", "improvements")


def downgrade() -> None:
    op.add_column("llm_reports", sa.Column("strengths", sa.Text(), nullable=True))
    op.add_column("llm_reports", sa.Column("improvements", sa.Text(), nullable=True))
    op.drop_column("llm_reports", "quantitative_metrics")
    op.drop_column("llm_reports", "score_breakdown")
