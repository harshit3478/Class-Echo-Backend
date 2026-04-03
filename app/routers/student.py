from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_student
from app.models.school import School
from app.models.class_ import Class
from app.models.subject import Subject
from app.models.recording import Recording
from app.schemas.school import SchoolOut
from app.schemas.class_ import ClassOut
from app.schemas.subject import SubjectOut
from app.schemas.recording import RecordingWithReport

router = APIRouter()


@router.get("/schools", response_model=list[SchoolOut])
async def list_schools(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_student),
):
    query = select(School).options(selectinload(School.admin))
    if search:
        query = query.where(School.name.ilike(f"%{search}%"))
    result = await db.execute(query.order_by(School.name))
    return result.scalars().all()


@router.get("/schools/{school_id}/classes", response_model=list[ClassOut])
async def list_classes(
    school_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_student),
):
    school = await db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    result = await db.execute(
        select(Class).where(Class.school_id == school_id).order_by(Class.name)
    )
    return result.scalars().all()


@router.get("/classes/{class_id}/subjects", response_model=list[SubjectOut])
async def list_subjects(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    student=Depends(get_student),
):
    class_ = await db.get(Class, class_id)
    if not class_ or class_.school_id != student.school_id:
        raise HTTPException(status_code=404, detail="Class not found")
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.teacher))
        .where(Subject.class_id == class_id)
        .order_by(Subject.name)
    )
    return result.scalars().all()


@router.get("/subjects/{subject_id}/recordings", response_model=list[RecordingWithReport])
async def list_recordings(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    student=Depends(get_student),
):
    # Verify subject belongs to student's class
    result = await db.execute(
        select(Subject)
        .join(Class, Subject.class_id == Class.id)
        .where(Subject.id == subject_id, Class.school_id == student.school_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    result = await db.execute(
        select(Recording)
        .options(selectinload(Recording.report))
        .where(Recording.subject_id == subject_id)
        .order_by(Recording.uploaded_at.desc())
    )
    return result.scalars().all()
