import asyncio
from datetime import datetime
from celery_worker import celery_app
from app.services.llm import analyze_recording


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_recording(self, recording_id: int, cloudinary_url: str):
    """
    Celery task: analyse a recording with the LLM stub and save the report.
    Uses a synchronous DB session (psycopg2) to avoid async complexity in Celery.
    """
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)

    try:
        with Session() as session:
            from app.models.recording import Recording, RecordingStatus
            from app.models.llm_report import LLMReport

            recording = session.get(Recording, recording_id)
            if not recording:
                return

            recording.status = RecordingStatus.processing
            session.commit()

            report_data = analyze_recording(cloudinary_url)

            report = LLMReport(
                recording_id=recording_id,
                overall_score=report_data["overall_score"],
                teaching_quality_notes=report_data["teaching_quality_notes"],
                score_breakdown=report_data["score_breakdown"],
                quantitative_metrics=report_data["quantitative_metrics"],
                raw_llm_response=report_data["raw_llm_response"],
            )
            session.add(report)

            recording.status = RecordingStatus.completed
            recording.processed_at = datetime.utcnow()
            session.commit()

    except Exception as exc:
        try:
            with Session() as session:
                from app.models.recording import Recording, RecordingStatus
                recording = session.get(Recording, recording_id)
                if recording:
                    recording.status = RecordingStatus.failed
                    session.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
