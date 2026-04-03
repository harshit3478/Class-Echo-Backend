from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class StudentSignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    mobile_number: str | None = None
    school_id: int
    class_id: int
