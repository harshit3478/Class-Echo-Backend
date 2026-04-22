from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


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
    school_id: int | None
    school_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeacherUpdate(BaseModel):
    name: str | None = None
