"""
Tests for School Admin routes (/school/...).

What these tests cover:
- CRUD on classes (scoped to own school only)
- CRUD on subjects + teacher assignment
- Teacher creation and listing
- Read-only access to recordings and reports
- Ownership enforcement: cannot touch another school's data
- Role guard: only 'school_admin' role can access
"""
from sqlalchemy import select

from app.models.class_ import Class
from app.models.school import School
from app.models.school_admin import SchoolAdmin
from app.models.subject import Subject


# ── Authorization ─────────────────────────────────────────────────────────────

async def test_unauthorized_no_token(client):
    resp = await client.get("/school/classes")
    assert resp.status_code == 401


async def test_unauthorized_wrong_role(client, student_token, student_user):
    resp = await client.get("/school/classes", headers={"Authorization": student_token})
    assert resp.status_code == 403


# ── Classes ───────────────────────────────────────────────────────────────────

async def test_list_classes(client, school_admin_token, school_admin_user, class_):
    resp = await client.get("/school/classes", headers={"Authorization": school_admin_token})
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert class_.id in ids


async def test_list_classes_empty(client, school_admin_token, school_admin_user):
    """No classes yet → empty list (not an error)."""
    resp = await client.get("/school/classes", headers={"Authorization": school_admin_token})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_class(client, school_admin_token, school_admin_user):
    resp = await client.post(
        "/school/classes",
        json={"name": "Class 7B"},
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Class 7B"
    assert data["school_id"] == school_admin_user.school_id


async def test_update_class(client, school_admin_token, class_):
    resp = await client.put(
        f"/school/classes/{class_.id}",
        json={"name": "Updated Class Name"},
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Class Name"


async def test_delete_class(client, db_session, school_admin_token, school_admin_user):
    # Create a class to delete (don't reuse the shared fixture — it would break other tests)
    new_class = Class(name="Temporary Class", school_id=school_admin_user.school_id)
    db_session.add(new_class)
    await db_session.commit()
    await db_session.refresh(new_class)

    resp = await client.delete(
        f"/school/classes/{new_class.id}",
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 204


async def test_get_class_from_other_school(client, db_session, school_admin_token):
    """
    School admin A should get 404 when trying to access a class from school B.
    """
    other_school = School(name="Other School")
    db_session.add(other_school)
    await db_session.commit()
    await db_session.refresh(other_school)

    other_class = Class(name="Class in Other School", school_id=other_school.id)
    db_session.add(other_class)
    await db_session.commit()
    await db_session.refresh(other_class)

    resp = await client.get(
        f"/school/classes/{other_class.id}",
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 404


# ── Subjects ──────────────────────────────────────────────────────────────────

async def test_list_subjects_empty(client, school_admin_token, class_):
    resp = await client.get(
        f"/school/classes/{class_.id}/subjects",
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_subject(client, school_admin_token, class_):
    resp = await client.post(
        f"/school/classes/{class_.id}/subjects",
        json={"name": "Science"},
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Science"
    assert data["teacher_id"] is None  # no teacher assigned yet


async def test_list_subjects_with_teacher(client, school_admin_token, subject, class_):
    """After assigning a teacher, the subject response includes teacher details."""
    resp = await client.get(
        f"/school/classes/{class_.id}/subjects",
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 200
    subjects = resp.json()
    assert any(s["id"] == subject.id for s in subjects)
    math = next(s for s in subjects if s["id"] == subject.id)
    assert math["teacher"] is not None
    assert math["teacher"]["id"] == subject.teacher_id


async def test_update_subject(client, school_admin_token, subject):
    resp = await client.put(
        f"/school/subjects/{subject.id}",
        json={"name": "Advanced Mathematics"},
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Advanced Mathematics"


async def test_assign_teacher_to_subject(client, db_session, school_admin_token, class_, school_admin_user):
    """Create a new subject without a teacher, then assign one."""
    from app.models.teacher import Teacher
    from app.core.security import hash_password

    # Create a second teacher to assign
    new_teacher = Teacher(
        name="New Teacher",
        email="newteacher@test.com",
        hashed_password=hash_password("pass"),
    )
    db_session.add(new_teacher)

    # Create subject with no teacher
    sub = Subject(name="History", class_id=class_.id)
    db_session.add(sub)
    await db_session.commit()
    await db_session.refresh(new_teacher)
    await db_session.refresh(sub)

    resp = await client.put(
        f"/school/subjects/{sub.id}/assign-teacher",
        json={"teacher_id": new_teacher.id},
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["teacher_id"] == new_teacher.id


async def test_assign_nonexistent_teacher(client, school_admin_token, subject):
    resp = await client.put(
        f"/school/subjects/{subject.id}/assign-teacher",
        json={"teacher_id": 99999},
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 404


# ── Teachers ──────────────────────────────────────────────────────────────────

async def test_create_teacher(client, school_admin_token, school_admin_user):
    resp = await client.post(
        "/school/teachers",
        json={
            "name": "Ms. Sharma",
            "email": "sharma@school.com",
            "password": "password123",
        },
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "sharma@school.com"
    assert "hashed_password" not in data  # never exposed in response


async def test_create_teacher_duplicate_email(client, school_admin_token, teacher_user):
    resp = await client.post(
        "/school/teachers",
        json={
            "name": "Another Teacher",
            "email": teacher_user.email,  # already registered
            "password": "password123",
        },
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 409


async def test_list_teachers(client, school_admin_token, teacher_user):
    resp = await client.get("/school/teachers", headers={"Authorization": school_admin_token})
    assert resp.status_code == 200
    emails = [t["email"] for t in resp.json()]
    assert teacher_user.email in emails


# ── Recordings & Reports (read-only) ─────────────────────────────────────────

async def test_list_subject_recordings_empty(client, school_admin_token, subject):
    resp = await client.get(
        f"/school/subjects/{subject.id}/recordings",
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_subject_reports_empty(client, school_admin_token, subject):
    resp = await client.get(
        f"/school/subjects/{subject.id}/reports",
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_recordings_for_other_school_subject(
    client, db_session, school_admin_token
):
    """School admin should get 404 for a subject that belongs to another school."""
    other_school = School(name="School B")
    db_session.add(other_school)

    other_sa = SchoolAdmin(
        name="Admin B",
        email="adminb@test.com",
        hashed_password="x",
        school_id=1,  # placeholder; will fix
    )

    await db_session.flush()
    other_sa.school_id = other_school.id
    db_session.add(other_sa)

    other_class = Class(name="Class X", school_id=other_school.id)
    db_session.add(other_class)
    await db_session.flush()

    other_subject = Subject(name="Art", class_id=other_class.id)
    db_session.add(other_subject)
    await db_session.commit()
    await db_session.refresh(other_subject)

    resp = await client.get(
        f"/school/subjects/{other_subject.id}/recordings",
        headers={"Authorization": school_admin_token},
    )
    assert resp.status_code == 404
