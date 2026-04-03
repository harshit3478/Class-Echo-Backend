from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_teacher
from app.models.subject import Subject
from app.models.recording import Recording
from app.models.student import Student
from app.schemas.subject import SubjectOut
from app.schemas.recording import RecordingWithReport, LLMReportOut
from app.services.cloudinary_service import upload_audio
from app.tasks.llm_tasks import process_recording

router = APIRouter()

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg",
    "audio/x-m4a", "audio/mp4", "audio/webm",
}


@router.get("/subjects", response_model=list[SubjectOut])
async def list_my_subjects(
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.teacher))
        .where(Subject.teacher_id == teacher.id)
        .order_by(Subject.name)
    )
    return result.scalars().all()


@router.get("/subjects/{subject_id}", response_model=SubjectOut)
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
    db: AsyncSession = Depends(get_db),
    teacher=Depends(get_teacher),
):
    await _get_teacher_subject(subject_id, teacher.id, db)

    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Upload an audio file.",
        )

    upload_result = await upload_audio(file, subject_id)

    recording = Recording(
        subject_id=subject_id,
        teacher_id=teacher.id,
        cloudinary_url=upload_result["url"],
        cloudinary_public_id=upload_result["public_id"],
        duration_seconds=upload_result.get("duration"),
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    # Enqueue async LLM processing
    process_recording.delay(recording.id, recording.cloudinary_url)

    return recording


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
        .options(selectinload(Subject.teacher))
        .where(Subject.id == subject_id, Subject.teacher_id == teacher_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found or not assigned to you")
    return subject
