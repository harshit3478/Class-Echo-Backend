from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Class(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    school: Mapped["School"] = relationship("School", back_populates="classes")
    subjects: Mapped[list["Subject"]] = relationship("Subject", back_populates="class_")
    students: Mapped[list["Student"]] = relationship("Student", back_populates="class_")
