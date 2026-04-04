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
from app.models.subject import Subject
from app.models.student import Student
from app.models.recording import Recording
from app.schemas.school import SchoolCreate, SchoolUpdate, SchoolOut
from app.schemas.class_ import ClassOut
from app.schemas.subject import SubjectOut
from app.schemas.student import StudentOut
from app.schemas.recording import RecordingWithReport

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

    for field, value in body.model_dump(exclude_unset=True).items():
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


@router.get("/schools/{school_id}/classes/{class_id}", response_model=ClassOut)
async def get_school_class(
    school_id: int,
    class_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    class_ = await _get_school_class(class_id, school_id, db)
    return class_


@router.get("/schools/{school_id}/classes/{class_id}/subjects", response_model=list[SubjectOut])
async def list_school_class_subjects(
    school_id: int,
    class_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    await _get_school_class(class_id, school_id, db)
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.teacher))
        .where(Subject.class_id == class_id)
        .order_by(Subject.name)
    )
    return result.scalars().all()


@router.get("/schools/{school_id}/subjects/{subject_id}/students", response_model=list[StudentOut])
async def list_school_subject_students(
    school_id: int,
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    subject = await _get_school_subject(subject_id, school_id, db)
    result = await db.execute(
        select(Student)
        .where(Student.class_id == subject.class_id)
        .order_by(Student.name)
    )
    return result.scalars().all()


@router.get("/schools/{school_id}/subjects/{subject_id}/recordings", response_model=list[RecordingWithReport])
async def list_school_subject_recordings(
    school_id: int,
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_admin),
):
    await _get_school_subject(subject_id, school_id, db)
    result = await db.execute(
        select(Recording)
        .options(selectinload(Recording.report))
        .where(Recording.subject_id == subject_id)
        .order_by(Recording.uploaded_at.desc())
    )
    return result.scalars().all()


async def _get_school_class(class_id: int, school_id: int, db: AsyncSession) -> Class:
    result = await db.execute(
        select(Class).where(Class.id == class_id, Class.school_id == school_id)
    )
    class_ = result.scalar_one_or_none()
    if not class_:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_


async def _get_school_subject(subject_id: int, school_id: int, db: AsyncSession) -> Subject:
    result = await db.execute(
        select(Subject)
        .join(Class, Subject.class_id == Class.id)
        .where(Subject.id == subject_id, Class.school_id == school_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject
