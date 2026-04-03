from datetime import datetime
from pydantic import BaseModel, ConfigDict


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


class StudentProfileOut(BaseModel):
    """Extended profile that includes resolved school and class names."""
    id: int
    name: str
    email: str
    mobile_number: str | None
    school_id: int
    school_name: str
    class_id: int
    class_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
