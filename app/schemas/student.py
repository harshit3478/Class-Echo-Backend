from datetime import datetime
from pydantic import BaseModel


class StudentOut(BaseModel):
    id: int
    name: str
    email: str
    mobile_number: str | None
    school_id: int
    class_id: int
    created_at: datetime

    class Config:
        from_attributes = True
