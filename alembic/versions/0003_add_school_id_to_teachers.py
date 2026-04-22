"""add school_id to teachers

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18

"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teachers",
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=True),
    )
    op.create_index("ix_teachers_school_id", "teachers", ["school_id"])


def downgrade() -> None:
    op.drop_index("ix_teachers_school_id", table_name="teachers")
    op.drop_column("teachers", "school_id")
