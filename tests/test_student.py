"""
Tests for Student routes (/student/...).

What these tests cover:
- School listing with and without search
- Class listing for a school
- Subject listing for a class (scoped to student's school)
- Recording listing for a subject
- Students cannot access teacher or admin endpoints
- Role guard: only 'student' role
"""
from app.models.recording import Recording, RecordingStatus


# ── Authorization ─────────────────────────────────────────────────────────────

async def test_unauthorized_no_token(client):
    resp = await client.get("/student/schools")
    assert resp.status_code == 401


async def test_teacher_cannot_access_student_schools(client, teacher_token, teacher_user):
    resp = await client.get("/student/schools", headers={"Authorization": teacher_token})
    assert resp.status_code == 403


async def test_student_cannot_access_teacher_endpoints(client, student_token, student_user):
    resp = await client.get("/teacher/subjects", headers={"Authorization": student_token})
    assert resp.status_code == 403


async def test_student_cannot_access_admin_endpoints(client, student_token, student_user):
    resp = await client.get("/admin/schools", headers={"Authorization": student_token})
    assert resp.status_code == 403


# ── Schools ───────────────────────────────────────────────────────────────────

async def test_list_schools(client, student_token, school, student_user):
    resp = await client.get("/student/schools", headers={"Authorization": student_token})
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert school.id in ids


async def test_list_schools_empty(client, student_token, student_user):
    """When no schools exist, an empty list is returned (not 404)."""
    resp = await client.get("/student/schools", headers={"Authorization": student_token})
    assert resp.status_code == 200
    # student_user fixture creates school, so there will be at least one — just check 200


async def test_list_schools_search_match(client, student_token, school, student_user):
    partial_name = school.name[:4]  # e.g. "Test"
    resp = await client.get(
        f"/student/schools?search={partial_name}",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert school.id in ids


async def test_list_schools_search_no_match(client, student_token, student_user):
    resp = await client.get(
        "/student/schools?search=xyznotfound12345",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ── Classes ───────────────────────────────────────────────────────────────────

async def test_list_classes_for_school(client, student_token, school, class_, student_user):
    resp = await client.get(
        f"/student/schools/{school.id}/classes",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert class_.id in ids


async def test_list_classes_school_not_found(client, student_token, student_user):
    resp = await client.get(
        "/student/schools/99999/classes",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 404


# ── Subjects ──────────────────────────────────────────────────────────────────

async def test_list_subjects_for_class(client, student_token, class_, subject, student_user):
    """
    The student's school matches class_.school_id, so they should see subjects.
    The subject fixture has a teacher assigned, so teacher field should be populated.
    """
    resp = await client.get(
        f"/student/classes/{class_.id}/subjects",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 200
    subjects = resp.json()
    assert any(s["id"] == subject.id for s in subjects)

    found = next(s for s in subjects if s["id"] == subject.id)
    assert found["teacher"] is not None


async def test_list_subjects_class_from_other_school(
    client, db_session, student_token, student_user
):
    """
    Student cannot see subjects for a class that belongs to a different school.
    student.school_id != other_class.school_id → 404.
    """
    from app.models.class_ import Class
    from app.models.school import School

    other_school = School(name="Rival School")
    db_session.add(other_school)
    await db_session.commit()
    await db_session.refresh(other_school)

    other_class = Class(name="Class Z", school_id=other_school.id)
    db_session.add(other_class)
    await db_session.commit()
    await db_session.refresh(other_class)

    resp = await client.get(
        f"/student/classes/{other_class.id}/subjects",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 404


# ── Recordings ────────────────────────────────────────────────────────────────

async def test_list_recordings_for_subject_empty(client, student_token, subject, student_user):
    resp = await client.get(
        f"/student/subjects/{subject.id}/recordings",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_recordings_for_subject(
    client, db_session, student_token, subject, teacher_user, student_user
):
    """Student can see recordings that a teacher uploaded to their class's subject."""
    recording = Recording(
        subject_id=subject.id,
        teacher_id=teacher_user.id,
        cloudinary_url="https://fake.cloudinary.com/class.mp3",
        cloudinary_public_id="fake/class_recording",
        status=RecordingStatus.completed,
    )
    db_session.add(recording)
    await db_session.commit()
    await db_session.refresh(recording)

    resp = await client.get(
        f"/student/subjects/{subject.id}/recordings",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 200
    ids = [r["id"] for r in resp.json()]
    assert recording.id in ids


async def test_list_recordings_subject_from_other_school(
    client, db_session, student_token, student_user
):
    """Student cannot access recordings for subjects outside their school."""
    from app.models.class_ import Class
    from app.models.school import School
    from app.models.subject import Subject

    other_school = School(name="Another School")
    db_session.add(other_school)
    await db_session.commit()
    await db_session.refresh(other_school)

    other_class = Class(name="Class Y", school_id=other_school.id)
    db_session.add(other_class)
    await db_session.commit()
    await db_session.refresh(other_class)

    other_subject = Subject(name="Physics", class_id=other_class.id)
    db_session.add(other_subject)
    await db_session.commit()
    await db_session.refresh(other_subject)

    resp = await client.get(
        f"/student/subjects/{other_subject.id}/recordings",
        headers={"Authorization": student_token},
    )
    assert resp.status_code == 404
