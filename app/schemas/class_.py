from datetime import datetime
from pydantic import BaseModel


class ClassCreate(BaseModel):
    name: str
    profile_image_url: str | None = None


class ClassUpdate(BaseModel):
    name: str | None = None
    profile_image_url: str | None = None


class ClassOut(BaseModel):
    id: int
    name: str
    profile_image_url: str | None
    school_id: int
    created_at: datetime

    class Config:
        from_attributes = True
