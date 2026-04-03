from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mobile_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"))
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    school: Mapped["School"] = relationship("School", back_populates="students")
    class_: Mapped["Class"] = relationship("Class", back_populates="students")
