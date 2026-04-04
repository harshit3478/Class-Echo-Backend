from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SchoolAdminProfileOut(BaseModel):
    id: int
    name: str
    email: str
    profile_pic_url: str | None
    school_id: int
    school_name: str
    school_logo_url: str | None
    school_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SchoolAdminUpdate(BaseModel):
    name: str | None = None
    school_name: str | None = None
    school_address: str | None = None
