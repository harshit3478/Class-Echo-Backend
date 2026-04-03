from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    class_: Mapped["Class"] = relationship("Class", back_populates="subjects")
    teacher: Mapped["Teacher | None"] = relationship("Teacher", back_populates="subjects")
    recordings: Mapped[list["Recording"]] = relationship("Recording", back_populates="subject")
