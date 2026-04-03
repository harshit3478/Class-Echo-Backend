from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.security import decode_token
from app.models.admin import Admin
from app.models.school_admin import SchoolAdmin
from app.models.teacher import Teacher
from app.models.student import Student

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(token)
        user_id: int = int(payload.get("sub"))
        role: str = payload.get("role")
    except (JWTError, TypeError, ValueError):
        raise CREDENTIALS_EXCEPTION

    model_map = {
        "admin": Admin,
        "school_admin": SchoolAdmin,
        "teacher": Teacher,
        "student": Student,
    }
    model = model_map.get(role)
    if not model:
        raise CREDENTIALS_EXCEPTION

    result = await db.execute(select(model).where(model.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise CREDENTIALS_EXCEPTION

    return user, role


def require_role(*roles: str):
    async def dependency(current=Depends(get_current_user)):
        user, role = current
        if role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return dependency


async def get_admin(current=Depends(get_current_user)):
    user, role = current
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_school_admin(current=Depends(get_current_user)):
    user, role = current
    if role != "school_admin":
        raise HTTPException(status_code=403, detail="School admin access required")
    return user


async def get_teacher(current=Depends(get_current_user)):
    user, role = current
    if role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user


async def get_student(current=Depends(get_current_user)):
    user, role = current
    if role != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    return user
