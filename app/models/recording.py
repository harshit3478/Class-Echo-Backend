import enum
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Float, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class RecordingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Recording(Base):
    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"))
    cloudinary_url: Mapped[str] = mapped_column(String(500))
    cloudinary_public_id: Mapped[str] = mapped_column(String(255))
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus), default=RecordingStatus.pending
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="recordings")
    teacher: Mapped["Teacher"] = relationship("Teacher", back_populates="recordings")
    report: Mapped["LLMReport | None"] = relationship("LLMReport", back_populates="recording", uselist=False)
