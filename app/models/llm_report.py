from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Float, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LLMReport(Base):
    __tablename__ = "llm_reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    recording_id: Mapped[int] = mapped_column(ForeignKey("recordings.id"), unique=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    teaching_quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvements: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    recording: Mapped["Recording"] = relationship("Recording", back_populates="report")
