"""
Tests for POST /auth/login and POST /auth/student/signup.

What these tests cover:
- Every role can log in with the right credentials
- Wrong password → 401
- Student self-signup: happy path, duplicate email, bad school/class
"""


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_login_wrong_password(client, admin_user):
    resp = await client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": "wrongpassword"},
    )
    assert resp.status_code == 401


async def test_login_nonexistent_user(client):
    resp = await client.post(
        "/auth/login",
        json={"email": "nobody@nowhere.com", "password": "whatever"},
    )
    assert resp.status_code == 401


async def test_login_admin(client, admin_user):
    resp = await client.post(
        "/auth/login",
        json={"email": admin_user.email, "password": "testpass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20  # non-empty JWT


async def test_login_school_admin(client, school_admin_user):
    resp = await client.post(
        "/auth/login",
        json={"email": school_admin_user.email, "password": "testpass"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "school_admin"


async def test_login_teacher(client, teacher_user):
    resp = await client.post(
        "/auth/login",
        json={"email": teacher_user.email, "password": "testpass"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "teacher"


async def test_login_student(client, student_user):
    resp = await client.post(
        "/auth/login",
        json={"email": student_user.email, "password": "testpass"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "student"


async def test_student_signup_success(client, school, class_):
    resp = await client.post(
        "/auth/student/signup",
        json={
            "name": "New Student",
            "email": "newstudent@test.com",
            "password": "password123",
            "mobile_number": "8888888888",
            "school_id": school.id,
            "class_id": class_.id,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["role"] == "student"
    assert len(data["access_token"]) > 20


async def test_student_signup_duplicate_email(client, student_user, school, class_):
    """Signing up with an already-registered email returns 409."""
    resp = await client.post(
        "/auth/student/signup",
        json={
            "name": "Duplicate",
            "email": student_user.email,  # already exists
            "password": "password123",
            "school_id": school.id,
            "class_id": class_.id,
        },
    )
    assert resp.status_code == 409


async def test_student_signup_bad_school(client, class_):
    """Signing up with a non-existent school_id returns 404."""
    resp = await client.post(
        "/auth/student/signup",
        json={
            "name": "Student",
            "email": "s2@test.com",
            "password": "pass",
            "school_id": 99999,
            "class_id": class_.id,
        },
    )
    assert resp.status_code == 404


async def test_student_signup_class_wrong_school(client, school, class_, db_session):
    """
    Signing up with a class that doesn't belong to the given school returns 404.
    We create a second school and try to use class_ (from the first school) with it.
    """
    from app.models.school import School

    other_school = School(name="Other School")
    db_session.add(other_school)
    await db_session.commit()
    await db_session.refresh(other_school)

    resp = await client.post(
        "/auth/student/signup",
        json={
            "name": "Student",
            "email": "s3@test.com",
            "password": "pass",
            "school_id": other_school.id,
            "class_id": class_.id,  # belongs to `school`, not `other_school`
        },
    )
    assert resp.status_code == 404
