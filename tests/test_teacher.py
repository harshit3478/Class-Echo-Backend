"""
Tests for Teacher routes (/teacher/...).

What these tests cover:
- Teacher sees only their own assigned subjects
- Recording upload (real Cloudinary call + Celery eager execution)
- After upload: the LLM report is created immediately (eager mode)
- Invalid file MIME type → 400
- Upload to unassigned subject → 404
- GET report before LLM has run → 404
- Role guard: only 'teacher' role

IMPORTANT about Celery:
Celery is configured with `task_always_eager=True` in conftest.py.
This means `process_recording.delay()` runs the task synchronously, inline.
The task uses its own psycopg2 connection and commits the LLMReport to the DB.
So by the time the test reads the DB after an upload, the report already exists.
"""
from sqlalchemy import select

from app.models.llm_report import LLMReport
from app.models.recording import Recording, RecordingStatus
from app.models.subject import Subject


# ── Authorization ─────────────────────────────────────────────────────────────

async def test_unauthorized_no_token(client):
    resp = await client.get("/teacher/subjects")
    assert resp.status_code == 401


async def test_student_cannot_access_teacher_endpoints(client, student_token, student_user):
    resp = await client.get("/teacher/subjects", headers={"Authorization": student_token})
    assert resp.status_code == 403


# ── Subjects ──────────────────────────────────────────────────────────────────

async def test_list_my_subjects(client, teacher_token, subject, teacher_user):
    """Teacher should see the subject assigned to them."""
    resp = await client.get("/teacher/subjects", headers={"Authorization": teacher_token})
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert subject.id in ids


async def test_list_subjects_excludes_unassigned(client, db_session, teacher_token, class_, teacher_user):
    """A subject not assigned to this teacher should not appear in the list."""
    unassigned = Subject(name="Geography", class_id=class_.id, teacher_id=None)
    db_session.add(unassigned)
    await db_session.commit()

    resp = await client.get("/teacher/subjects", headers={"Authorization": teacher_token})
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert unassigned.id not in ids


async def test_get_subject_detail(client, teacher_token, subject):
    resp = await client.get(
        f"/teacher/subjects/{subject.id}",
        headers={"Authorization": teacher_token},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == subject.id


async def test_get_unassigned_subject_returns_404(client, db_session, teacher_token, class_):
    unassigned = Subject(name="Chemistry", class_id=class_.id, teacher_id=None)
    db_session.add(unassigned)
    await db_session.commit()
    await db_session.refresh(unassigned)

    resp = await client.get(
        f"/teacher/subjects/{unassigned.id}",
        headers={"Authorization": teacher_token},
    )
    assert resp.status_code == 404


# ── Recordings ────────────────────────────────────────────────────────────────

async def test_list_recordings_empty(client, teacher_token, subject):
    resp = await client.get(
        f"/teacher/subjects/{subject.id}/recordings",
        headers={"Authorization": teacher_token},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_upload_recording(client, teacher_token, subject, audio_bytes):
    """
    Upload a real WAV file → Cloudinary stores it, Celery (eager) processes it.
    Response status is 'pending' (captured before Celery runs in the route).
    The Cloudinary URL should be a real https:// URL.
    """
    resp = await client.post(
        f"/teacher/subjects/{subject.id}/recordings",
        headers={"Authorization": teacher_token},
        files={"file": ("test_audio.wav", audio_bytes, "audio/wav")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["subject_id"] == subject.id
    assert data["status"] == "pending"  # in-memory state at route response time
    assert data["cloudinary_url"].startswith("https://")
    assert data["cloudinary_url"] != ""


async def test_upload_creates_llm_report(client, db_session, teacher_token, subject, audio_bytes):
    """
    After upload, the Celery task (eager) runs and creates an LLMReport.
    Querying the DB directly should show the report with the mock score.
    Also, the Recording status should be updated to 'completed' by the task.
    """
    resp = await client.post(
        f"/teacher/subjects/{subject.id}/recordings",
        headers={"Authorization": teacher_token},
        files={"file": ("test_audio.wav", audio_bytes, "audio/wav")},
    )
    assert resp.status_code == 201
    recording_id = resp.json()["id"]

    # LLMReport should exist (committed by Celery task's psycopg2 session)
    result = await db_session.execute(
        select(LLMReport).where(LLMReport.recording_id == recording_id)
    )
    report = result.scalar_one_or_none()
    assert report is not None
    assert report.overall_score == 7.5  # from the mock LLM stub
    assert report.strengths is not None

    # Recording status should be 'completed'
    result2 = await db_session.execute(
        select(Recording).where(Recording.id == recording_id)
    )
    recording = result2.scalar_one()
    assert recording.status == RecordingStatus.completed
    assert recording.processed_at is not None


async def test_upload_invalid_mime_type(client, teacher_token, subject):
    """Uploading a non-audio file (text/plain) should return 400."""
    resp = await client.post(
        f"/teacher/subjects/{subject.id}/recordings",
        headers={"Authorization": teacher_token},
        files={"file": ("notes.txt", b"this is not audio", "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_to_unassigned_subject(client, db_session, teacher_token, class_, audio_bytes):
    """Teacher cannot upload to a subject they're not assigned to."""
    unassigned = Subject(name="Biology", class_id=class_.id, teacher_id=None)
    db_session.add(unassigned)
    await db_session.commit()
    await db_session.refresh(unassigned)

    resp = await client.post(
        f"/teacher/subjects/{unassigned.id}/recordings",
        headers={"Authorization": teacher_token},
        files={"file": ("test.wav", audio_bytes, "audio/wav")},
    )
    assert resp.status_code == 404


# ── Reports ───────────────────────────────────────────────────────────────────

async def test_get_report_no_report_yet(client, db_session, teacher_token, subject, teacher_user):
    """
    If a recording exists but the LLM hasn't processed it yet (no LLMReport row),
    the endpoint should return 404.
    """
    # Create a recording manually, without triggering Celery
    recording = Recording(
        subject_id=subject.id,
        teacher_id=teacher_user.id,
        cloudinary_url="https://fake.cloudinary.com/test.mp3",
        cloudinary_public_id="fake/test",
        status=RecordingStatus.pending,
    )
    db_session.add(recording)
    await db_session.commit()
    await db_session.refresh(recording)

    resp = await client.get(
        f"/teacher/recordings/{recording.id}/report",
        headers={"Authorization": teacher_token},
    )
    assert resp.status_code == 404
    assert "not yet available" in resp.json()["detail"]


async def test_get_report_success(client, db_session, teacher_token, subject, teacher_user):
    """
    If an LLMReport exists for a recording, the teacher can fetch it.
    """
    # Create recording + report directly in DB
    recording = Recording(
        subject_id=subject.id,
        teacher_id=teacher_user.id,
        cloudinary_url="https://fake.cloudinary.com/test.mp3",
        cloudinary_public_id="fake/test2",
        status=RecordingStatus.completed,
    )
    db_session.add(recording)
    await db_session.flush()

    report = LLMReport(
        recording_id=recording.id,
        overall_score=8.0,
        teaching_quality_notes="Great class",
        strengths="Clear explanation",
        improvements="More examples needed",
        raw_llm_response={"model": "stub"},
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(recording)

    resp = await client.get(
        f"/teacher/recordings/{recording.id}/report",
        headers={"Authorization": teacher_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_score"] == 8.0
    assert data["strengths"] == "Clear explanation"


async def test_cannot_get_other_teachers_report(
    client, db_session, teacher_token, class_, subject
):
    """Teacher A cannot access a recording that belongs to Teacher B."""
    from app.core.security import hash_password
    from app.models.teacher import Teacher

    teacher_b = Teacher(
        name="Teacher B",
        email="teacherb@test.com",
        hashed_password=hash_password("pass"),
    )
    db_session.add(teacher_b)
    await db_session.flush()

    recording_b = Recording(
        subject_id=subject.id,
        teacher_id=teacher_b.id,
        cloudinary_url="https://fake.cloudinary.com/b.mp3",
        cloudinary_public_id="fake/b",
    )
    db_session.add(recording_b)
    await db_session.commit()
    await db_session.refresh(recording_b)

    resp = await client.get(
        f"/teacher/recordings/{recording_b.id}/report",
        headers={"Authorization": teacher_token},  # teacher A's token
    )
    # Route filters by teacher_id=current_teacher.id, so this recording is not found
    assert resp.status_code == 404
