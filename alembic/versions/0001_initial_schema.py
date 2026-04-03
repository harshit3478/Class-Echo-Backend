"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("profile_pic_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "teachers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("profile_image_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "school_admins",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("profile_pic_url", sa.String(500), nullable=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("profile_image_url", sa.String(500), nullable=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("profile_image_url", sa.String(500), nullable=True),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("profile_image_url", sa.String(500), nullable=True),
        sa.Column("mobile_number", sa.String(20), nullable=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


    op.create_table(
        "recordings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("teacher_id", sa.Integer(), sa.ForeignKey("teachers.id"), nullable=False),
        sa.Column("cloudinary_url", sa.String(500), nullable=False),
        sa.Column("cloudinary_public_id", sa.String(255), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.Enum("pending", "processing", "completed", "failed", name="recordingstatus"), nullable=False, server_default="pending"),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "llm_reports",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("recording_id", sa.Integer(), sa.ForeignKey("recordings.id"), unique=True, nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("teaching_quality_notes", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("improvements", sa.Text(), nullable=True),
        sa.Column("raw_llm_response", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_reports")
    op.drop_table("recordings")
    op.execute("DROP TYPE IF EXISTS recordingstatus")
    op.drop_table("students")
    op.drop_table("subjects")
    op.drop_table("classes")
    op.drop_table("school_admins")
    op.drop_table("teachers")
    op.drop_table("schools")
    op.drop_table("admins")
