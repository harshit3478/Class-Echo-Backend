from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_admin
from app.core.security import hash_password
from app.models.school import School
from app.models.school_admin import SchoolAdmin
from app.models.class_ import Class
from app.schemas.school import SchoolCreate, SchoolUpdate, SchoolOut
from app.schemas.class_ import ClassOut

router = APIRouter()


@router.get("/schools", response_model=list[SchoolOut])
async def list_schools(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    result = await db.execute(
        select(School).options(selectinload(School.admin)).order_by(School.created_at.desc())
    )
    return result.scalars().all()


@router.post("/schools", response_model=SchoolOut, status_code=201)
async def create_school(
    body: SchoolCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    # Check admin email not already taken
    from app.models.admin import Admin
    from app.models.teacher import Teacher
    from app.models.student import Student
    for Model in (Admin, SchoolAdmin, Teacher, Student):
        r = await db.execute(select(Model).where(Model.email == body.admin_email))
        if r.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Admin email already registered")

    school = School(name=body.name, address=body.address, logo_url=body.logo_url)
    db.add(school)
    await db.flush()  # get school.id

    school_admin = SchoolAdmin(
        name=body.admin_name,
        email=body.admin_email,
        hashed_password=hash_password(body.admin_password),
        school_id=school.id,
    )
    db.add(school_admin)
    await db.commit()
    await db.refresh(school)

    result = await db.execute(
        select(School).options(selectinload(School.admin)).where(School.id == school.id)
    )
    return result.scalar_one()


@router.get("/schools/{school_id}", response_model=SchoolOut)
async def get_school(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    result = await db.execute(
        select(School).options(selectinload(School.admin)).where(School.id == school_id)
    )
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    return school


@router.put("/schools/{school_id}", response_model=SchoolOut)
async def update_school(
    school_id: int,
    body: SchoolUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    result = await db.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(school, field, value)
    await db.commit()
    await db.refresh(school)

    result = await db.execute(
        select(School).options(selectinload(School.admin)).where(School.id == school.id)
    )
    return result.scalar_one()


@router.delete("/schools/{school_id}", status_code=204)
async def delete_school(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    result = await db.execute(select(School).where(School.id == school_id))
    school = result.scalar_one_or_none()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    await db.delete(school)
    await db.commit()


@router.get("/schools/{school_id}/classes", response_model=list[ClassOut])
async def list_school_classes(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    result = await db.execute(
        select(Class).where(Class.school_id == school_id).order_by(Class.name)
    )
    return result.scalars().all()
