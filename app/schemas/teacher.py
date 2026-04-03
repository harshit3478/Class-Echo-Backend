from datetime import datetime
from pydantic import BaseModel, EmailStr


class TeacherCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    profile_image_url: str | None = None


class TeacherOut(BaseModel):
    id: int
    name: str
    email: str
    profile_image_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True
