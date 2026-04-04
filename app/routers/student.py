from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_student
from app.models.school import School
from app.models.class_ import Class
from app.models.subject import Subject
from app.models.recording import Recording
from app.models.student import Student
from app.schemas.school import SchoolOut
from app.schemas.class_ import ClassOut
from app.schemas.subject import SubjectOut
from app.schemas.recording import RecordingWithReport
from app.schemas.student import StudentProfileOut, StudentUpdate
from app.services.cloudinary_service import upload_image

router = APIRouter()


@router.get("/me", response_model=StudentProfileOut)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    student=Depends(get_student),
):
    result = await db.execute(
        select(Student)
        .options(selectinload(Student.school), selectinload(Student.class_))
        .where(Student.id == student.id)
    )
    return _build_student_profile(result.scalar_one())


@router.put("/me", response_model=StudentProfileOut)
async def update_my_profile(
    body: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    student=Depends(get_student),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(student, field, value)
    await db.commit()
    return await get_my_profile(db=db, student=student)


@router.post("/profile-image", response_model=StudentProfileOut)
async def upload_profile_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    student=Depends(get_student),
):
    result = await upload_image(file, folder=f"classecho/students/{student.id}")
    student.profile_image_url = result["url"]
    await db.commit()
    return await get_my_profile(db=db, student=student)


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


def _build_student_profile(student: Student) -> StudentProfileOut:
    return StudentProfileOut(
        id=student.id,
        name=student.name,
        email=student.email,
        profile_image_url=student.profile_image_url,
        mobile_number=student.mobile_number,
        school_id=student.school_id,
        school_name=student.school.name,
        class_id=student.class_id,
        class_name=student.class_.name,
        created_at=student.created_at,
    )
