"""
Tests for Super Admin routes (/admin/...).

What these tests cover:
- Full CRUD on schools
- Auto-creation of SchoolAdmin when a school is created
- Email uniqueness enforcement across all user tables
- Role guard: only 'admin' role can access these endpoints
"""
from sqlalchemy import select

from app.models.school_admin import SchoolAdmin


SCHOOL_PAYLOAD = {
    "name": "Springfield Elementary",
    "address": "742 Evergreen Terrace",
    "logo_url": None,
    "admin_name": "Principal Skinner",
    "admin_email": "skinner@springfield.edu",
    "admin_password": "secret123",
}


# ── Authorization ─────────────────────────────────────────────────────────────

async def test_unauthenticated(client):
    resp = await client.get("/admin/schools")
    assert resp.status_code == 401


async def test_teacher_cannot_access_admin(client, teacher_token):
    resp = await client.get("/admin/schools", headers={"Authorization": teacher_token})
    assert resp.status_code == 403


async def test_student_cannot_access_admin(client, student_token, student_user):
    resp = await client.get("/admin/schools", headers={"Authorization": student_token})
    assert resp.status_code == 403


# ── List & Get ────────────────────────────────────────────────────────────────

async def test_list_schools_empty(client, admin_user, admin_token):
    resp = await client.get("/admin/schools", headers={"Authorization": admin_token})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_schools(client, admin_token, school):
    resp = await client.get("/admin/schools", headers={"Authorization": admin_token})
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert school.id in ids


async def test_get_school(client, admin_token, school):
    resp = await client.get(f"/admin/schools/{school.id}", headers={"Authorization": admin_token})
    assert resp.status_code == 200
    assert resp.json()["id"] == school.id
    assert resp.json()["name"] == school.name


async def test_get_school_not_found(client, admin_token, admin_user):
    resp = await client.get("/admin/schools/99999", headers={"Authorization": admin_token})
    assert resp.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────

async def test_create_school(client, admin_token, admin_user):
    resp = await client.post(
        "/admin/schools",
        json=SCHOOL_PAYLOAD,
        headers={"Authorization": admin_token},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == SCHOOL_PAYLOAD["name"]
    assert data["admin"]["email"] == SCHOOL_PAYLOAD["admin_email"]


async def test_create_school_auto_creates_admin(client, db_session, admin_token, admin_user):
    """After creating a school, a SchoolAdmin row must exist linked to it."""
    resp = await client.post(
        "/admin/schools",
        json=SCHOOL_PAYLOAD,
        headers={"Authorization": admin_token},
    )
    assert resp.status_code == 201
    school_id = resp.json()["id"]

    result = await db_session.execute(
        select(SchoolAdmin).where(SchoolAdmin.school_id == school_id)
    )
    school_admin = result.scalar_one_or_none()
    assert school_admin is not None
    assert school_admin.email == SCHOOL_PAYLOAD["admin_email"]


async def test_create_school_duplicate_admin_email(client, admin_token, admin_user):
    """Creating two schools with the same admin email returns 409."""
    await client.post(
        "/admin/schools", json=SCHOOL_PAYLOAD, headers={"Authorization": admin_token}
    )
    resp = await client.post(
        "/admin/schools",
        json={**SCHOOL_PAYLOAD, "name": "Another School"},
        headers={"Authorization": admin_token},
    )
    assert resp.status_code == 409


# ── Update ────────────────────────────────────────────────────────────────────

async def test_update_school_name(client, admin_token, school):
    resp = await client.put(
        f"/admin/schools/{school.id}",
        json={"name": "Renamed School"},
        headers={"Authorization": admin_token},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed School"


async def test_update_school_not_found(client, admin_token, admin_user):
    resp = await client.put(
        "/admin/schools/99999",
        json={"name": "Ghost School"},
        headers={"Authorization": admin_token},
    )
    assert resp.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

async def test_delete_school(client, admin_token, school):
    resp = await client.delete(
        f"/admin/schools/{school.id}", headers={"Authorization": admin_token}
    )
    assert resp.status_code == 204

    # Verify it's gone
    resp = await client.get(
        f"/admin/schools/{school.id}", headers={"Authorization": admin_token}
    )
    assert resp.status_code == 404


async def test_delete_school_not_found(client, admin_token, admin_user):
    resp = await client.delete("/admin/schools/99999", headers={"Authorization": admin_token})
    assert resp.status_code == 404


# ── School classes (view-only for admin) ─────────────────────────────────────

async def test_list_school_classes_empty(client, admin_token, school):
    resp = await client.get(
        f"/admin/schools/{school.id}/classes", headers={"Authorization": admin_token}
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_school_classes(client, admin_token, school, class_):
    resp = await client.get(
        f"/admin/schools/{school.id}/classes", headers={"Authorization": admin_token}
    )
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert class_.id in ids
