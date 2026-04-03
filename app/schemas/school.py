from datetime import datetime
from pydantic import BaseModel, EmailStr


class SchoolCreate(BaseModel):
    name: str
    address: str | None = None
    logo_url: str | None = None
    # School admin details (auto-created with school)
    admin_name: str
    admin_email: EmailStr
    admin_password: str


class SchoolUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    logo_url: str | None = None


class SchoolAdminOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class SchoolOut(BaseModel):
    id: int
    name: str
    address: str | None
    logo_url: str | None
    created_at: datetime
    admin: SchoolAdminOut | None = None

    class Config:
        from_attributes = True
