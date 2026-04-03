"""
Shared fixtures for ScholarMetric test suite.

How test isolation works:
- All tables are created ONCE at the start of the test session (setup_db).
- After EVERY test, all rows are deleted (clean_db autouse fixture).
- Each test therefore starts with a completely empty database.
- Tables themselves are NEVER dropped — they are your production tables.

How Celery works in tests:
- task_always_eager=True makes .delay() run the task synchronously (in-process).
- No Celery worker needs to be running, but Redis must be up (docker-compose up -d).
- The Celery task commits via its own psycopg2 connection, so the LLM report
  row is immediately visible in the DB after a recording upload.

Real external services used:
- Cloudinary: real uploads happen; test files are cleaned up at session end.
- Redis: must be running for Celery (even in eager mode it needs the broker).
- PostgreSQL (Neon): must be reachable and DATABASE_URL set in .env.
"""
import io
import wave

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

import app.models  # noqa: F401 — registers all models with Base.metadata
from app.core.security import create_access_token, hash_password
from app.database import AsyncSessionLocal, Base, engine, get_db
from app.main import app
from app.models.admin import Admin
from app.models.class_ import Class
from app.models.recording import Recording
from app.models.school import School
from app.models.school_admin import SchoolAdmin
from app.models.student import Student
from app.models.subject import Subject
from app.models.teacher import Teacher

# ── Celery: run tasks synchronously during tests ──────────────────────────────
from celery_worker import celery_app

celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

# ── Track Cloudinary uploads so we can clean them up after the session ────────
_cloudinary_uploads: list[str] = []


# =============================================================================
# SESSION-SCOPED FIXTURES (run once for the whole test run)
# =============================================================================


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """
    Create all DB tables before the test session starts.
    Uses checkfirst=True (default) so it's safe to call even if tables exist.
    Does NOT drop tables at the end — they are your production tables.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture(scope="session", autouse=True)
def cleanup_cloudinary(setup_db):
    """Delete all Cloudinary test uploads after the whole test session ends."""
    yield
    import cloudinary.uploader

    for public_id in _cloudinary_uploads:
        try:
            cloudinary.uploader.destroy(public_id, resource_type="video")
        except Exception:
            pass  # best-effort — don't fail teardown


@pytest.fixture(scope="session")
def audio_bytes():
    """
    A minimal valid WAV file (0.5 sec of silence).
    Used as the upload payload in recording tests.
    Cloudinary accepts WAV under resource_type='video'.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)     # mono
        wav_file.setsampwidth(2)     # 16-bit samples
        wav_file.setframerate(8000)  # 8 kHz
        wav_file.writeframes(b"\x00\x00" * 4000)  # 4000 frames = 0.5 s
    buffer.seek(0)
    return buffer.read()


# =============================================================================
# FUNCTION-SCOPED FIXTURES (run for each individual test)
# =============================================================================


@pytest_asyncio.fixture(autouse=True)
async def clean_db(setup_db):
    """
    Runs after EVERY test:
    1. Collects any Cloudinary public_ids from the recordings table for later cleanup.
    2. Deletes all rows from all tables in reverse FK order.

    This ensures each test starts with an empty DB.
    """
    yield  # test runs here

    # Collect cloudinary IDs before wiping (best-effort)
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Recording.cloudinary_public_id))
            for (public_id,) in result:
                if public_id:
                    _cloudinary_uploads.append(public_id)
    except Exception:
        pass

    # Delete all rows, in reverse FK-dependency order
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def db_session():
    """
    Async DB session for use inside tests when you need to query the DB directly
    (e.g. to verify a row was created by a route).
    """
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """
    HTTP test client.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# =============================================================================
# DATA FIXTURES — insert standard test entities into the DB
# =============================================================================


@pytest_asyncio.fixture
async def admin_user(db_session):
    admin = Admin(
        name="Super Admin",
        email="admin@test.com",
        hashed_password=hash_password("testpass"),
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
def admin_token(admin_user):
    token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
    return f"Bearer {token}"


@pytest_asyncio.fixture
async def school(db_session):
    s = School(name="Test School", address="123 Main Street")
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def school_admin_user(db_session, school):
    sa = SchoolAdmin(
        name="School Admin",
        email="schooladmin@test.com",
        hashed_password=hash_password("testpass"),
        school_id=school.id,
    )
    db_session.add(sa)
    await db_session.commit()
    await db_session.refresh(sa)
    return sa


@pytest.fixture
def school_admin_token(school_admin_user):
    token = create_access_token({
        "sub": str(school_admin_user.id),
        "role": "school_admin",
        "school_id": school_admin_user.school_id,
    })
    return f"Bearer {token}"


@pytest_asyncio.fixture
async def class_(db_session, school):
    c = Class(name="Class 6A", school_id=school.id)
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest_asyncio.fixture
async def teacher_user(db_session):
    t = Teacher(
        name="Test Teacher",
        email="teacher@test.com",
        hashed_password=hash_password("testpass"),
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)
    return t


@pytest.fixture
def teacher_token(teacher_user):
    token = create_access_token({"sub": str(teacher_user.id), "role": "teacher"})
    return f"Bearer {token}"


@pytest_asyncio.fixture
async def subject(db_session, class_, teacher_user):
    """A subject in class_, assigned to teacher_user."""
    s = Subject(name="Mathematics", class_id=class_.id, teacher_id=teacher_user.id)
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s


@pytest_asyncio.fixture
async def student_user(db_session, school, class_):
    st = Student(
        name="Test Student",
        email="student@test.com",
        hashed_password=hash_password("testpass"),
        mobile_number="9999999999",
        school_id=school.id,
        class_id=class_.id,
    )
    db_session.add(st)
    await db_session.commit()
    await db_session.refresh(st)
    return st


@pytest.fixture
def student_token(student_user):
    token = create_access_token({"sub": str(student_user.id), "role": "student"})
    return f"Bearer {token}"
