from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import verify_password, hash_password, create_access_token
from app.schemas.auth import LoginRequest, TokenResponse, StudentSignupRequest
from app.models.admin import Admin
from app.models.school_admin import SchoolAdmin
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.school import School
from app.models.class_ import Class

router = APIRouter()

ROLE_MODELS = [
    ("admin", Admin),
    ("school_admin", SchoolAdmin),
    ("teacher", Teacher),
    ("student", Student),
]


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    for role, Model in ROLE_MODELS:
        result = await db.execute(select(Model).where(Model.email == body.email))
        user = result.scalar_one_or_none()
        if user and verify_password(body.password, user.hashed_password):
            token_data = {"sub": str(user.id), "role": role}
            if role == "school_admin":
                token_data["school_id"] = user.school_id
            token = create_access_token(token_data)
            return TokenResponse(access_token=token, role=role)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )


@router.post("/student/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def student_signup(body: StudentSignupRequest, db: AsyncSession = Depends(get_db)):
    # Validate school and class exist
    school = await db.get(School, body.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    class_ = await db.get(Class, body.class_id)
    if not class_ or class_.school_id != body.school_id:
        raise HTTPException(status_code=404, detail="Class not found in this school")

    # Check email not already taken across all user tables
    for _, Model in ROLE_MODELS:
        result = await db.execute(select(Model).where(Model.email == body.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

    student = Student(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        mobile_number=body.mobile_number,
        school_id=body.school_id,
        class_id=body.class_id,
    )
    db.add(student)
    await db.commit()
    await db.refresh(student)

    token = create_access_token({"sub": str(student.id), "role": "student"})
    return TokenResponse(access_token=token, role="student")
