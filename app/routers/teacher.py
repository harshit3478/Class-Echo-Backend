from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_teacher
from app.models.subject import Subject
from app.models.recording import Recording
from app.models.student import Student
from app.schemas.subject import SubjectOut, SubjectWithClassOut
from app.schemas.recording import RecordingWithReport, LLMReportOut
from app.schemas.student import StudentOut
from app.schemas.teacher import TeacherOut, TeacherUpdate
from app.services.cloudinary_service import upload_audio, upload_image
from app.tasks.llm_tasks import process_recording

router = APIRouter()


def _teacher_out(teacher) -> TeacherOut:
    return TeacherOut(
        id=teacher.id,
        name=teacher.name,
        email=teacher.email,
        profile_image_url=teacher.profile_image_url,
        school_id=teacher.school_id,
        school_name=teacher.school.name if teacher.school else None,
        created_at=teacher.created_at,
    )


ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/ogg",
    "audio/x-m4a",
    "audio/mp4",
    "audio/webm",
    "audio/aac",
}

EXT_TO_MIME = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "webm": "audio/webm",
    "aac": "audio/aac",
}


def _resolve_mime(file: UploadFile) -> str:
    """Return MIME type, falling back to extension if content_type is unreliable."""
    ct = (file.content_type or "").split(";")[0].strip().lower()
    if ct in ALLOWED_AUDIO_TYPES:
        return ct
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    return EXT_TO_MIME.get(ext, ct)


@router.get("/me", response_model=TeacherOut)
async def get_my_profile(teacher=Depends(get_teacher)):
    return _teacher_out(teacher)


@router.put("/me", response_model=TeacherOut)
async def update_my_profile(
    body: TeacherUpdate,
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(teacher, field, value)
    await db.commit()
    await db.refresh(teacher)
    return _teacher_out(teacher)


@router.post("/profile-image", response_model=TeacherOut)
async def upload_profile_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    result = await upload_image(file, folder=f"classecho/teachers/{teacher.id}")
    teacher.profile_image_url = result["url"]
    await db.commit()
    await db.refresh(teacher)
    return _teacher_out(teacher)


@router.get("/subjects/{subject_id}/students", response_model=list[StudentOut])
async def list_subject_students(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    subject = await _get_teacher_subject(subject_id, teacher.id, db)
    result = await db.execute(
        select(Student)
        .where(Student.class_id == subject.class_id)
        .order_by(Student.name)
    )
    return result.scalars().all()


@router.get("/subjects", response_model=list[SubjectWithClassOut])
async def list_my_subjects(
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.teacher), selectinload(Subject.class_))
        .where(Subject.teacher_id == teacher.id)
        .order_by(Subject.name)
    )
    return result.scalars().all()


@router.get("/subjects/{subject_id}", response_model=SubjectWithClassOut)
async def get_my_subject(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    subject = await _get_teacher_subject(subject_id, teacher.id, db)
    return subject


@router.get("/subjects/{subject_id}/recordings", response_model=list[RecordingWithReport])
async def list_recordings(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    await _get_teacher_subject(subject_id, teacher.id, db)
    result = await db.execute(
        select(Recording)
        .options(selectinload(Recording.report))
        .where(Recording.subject_id == subject_id, Recording.teacher_id == teacher.id)
        .order_by(Recording.uploaded_at.desc())
    )
    return result.scalars().all()


@router.post("/subjects/{subject_id}/recordings", response_model=RecordingWithReport, status_code=201)
async def upload_recording(
    subject_id: int,
    file: UploadFile = File(...),
    chapter_name: str | None = Form(None),
    description: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    await _get_teacher_subject(subject_id, teacher.id, db)

    mime = _resolve_mime(file)
    if mime not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Upload an audio file.",
        )

    upload_result = await upload_audio(file, subject_id)

    recording = Recording(
        subject_id=subject_id,
        teacher_id=teacher.id,
        chapter_name=chapter_name or None,
        description=description or None,
        cloudinary_url=upload_result["url"],
        cloudinary_public_id=upload_result["public_id"],
        duration_seconds=upload_result.get("duration"),
    )
    db.add(recording)
    await db.commit()

    # Enqueue async LLM processing
    process_recording.delay(recording.id, recording.cloudinary_url)

    result = await db.execute(
        select(Recording)
        .options(selectinload(Recording.report))
        .where(Recording.id == recording.id)
    )
    return result.scalar_one()


@router.get("/recordings/{recording_id}/report", response_model=LLMReportOut)
async def get_report(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    result = await db.execute(
        select(Recording)
        .options(selectinload(Recording.report))
        .where(Recording.id == recording_id, Recording.teacher_id == teacher.id)
    )
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    if not recording.report:
        raise HTTPException(status_code=404, detail="Report not yet available")
    return recording.report


async def _get_teacher_subject(subject_id: int, teacher_id: int, db: AsyncSession) -> Subject:
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.teacher), selectinload(Subject.class_))
        .where(Subject.id == subject_id, Subject.teacher_id == teacher_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or not assigned to you")
    return subject
