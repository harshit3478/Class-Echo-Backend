from datetime import datetime
from pydantic import BaseModel
from app.models.recording import RecordingStatus


class RecordingOut(BaseModel):
    id: int
    subject_id: int
    teacher_id: int
    chapter_name: str | None
    description: str | None
    cloudinary_url: str
    duration_seconds: float | None
    status: RecordingStatus
    uploaded_at: datetime
    processed_at: datetime | None

    class Config:
        from_attributes = True


class LLMReportOut(BaseModel):
    id: int
    recording_id: int
    overall_score: float | None
    teaching_quality_notes: str | None
    strengths: str | None
    improvements: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class RecordingWithReport(RecordingOut):
    report: LLMReportOut | None = None
