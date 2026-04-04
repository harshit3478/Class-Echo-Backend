from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_school_admin
from app.models.class_ import Class
from app.models.school import School
from app.models.school_admin import SchoolAdmin
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.recording import Recording
from app.models.llm_report import LLMReport
from app.schemas.class_ import ClassCreate, ClassUpdate, ClassOut
from app.schemas.school import SchoolOut
from app.schemas.school_admin import SchoolAdminProfileOut, SchoolAdminUpdate
from app.schemas.subject import SubjectCreate, SubjectUpdate, SubjectOut, AssignTeacherRequest
from app.schemas.teacher import TeacherCreate, TeacherOut
from app.schemas.recording import RecordingWithReport, LLMReportOut
from app.schemas.student import StudentOut, StudentWithClassOut
from app.core.security import hash_password
from app.services.cloudinary_service import upload_image

router = APIRouter()


@router.get("/me", response_model=SchoolAdminProfileOut)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    admin = await _get_school_admin_with_school(school_admin.id, db)
    return _build_school_admin_profile(admin)


@router.put("/me", response_model=SchoolAdminProfileOut)
async def update_my_profile(
    body: SchoolAdminUpdate,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    payload = body.model_dump(exclude_unset=True)
    school = await db.get(School, school_admin.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    if "name" in payload:
        school_admin.name = payload["name"]
    if "school_name" in payload:
        school.name = payload["school_name"]
    if "school_address" in payload:
        school.address = payload["school_address"]

    await db.commit()
    admin = await _get_school_admin_with_school(school_admin.id, db)
    return _build_school_admin_profile(admin)


@router.post("/profile-image", response_model=SchoolAdminProfileOut)
async def upload_profile_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    result = await upload_image(file, folder=f"classecho/school-admins/{school_admin.id}")
    school_admin.profile_pic_url = result["url"]
    await db.commit()
    admin = await _get_school_admin_with_school(school_admin.id, db)
    return _build_school_admin_profile(admin)


@router.post("/logo", response_model=SchoolOut)
async def upload_school_logo(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    result = await upload_image(file, folder=f"classecho/schools/{school_admin.school_id}")
    school = await db.get(School, school_admin.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    school.logo_url = result["url"]
    await db.commit()
    result = await db.execute(
        select(School)
        .options(selectinload(School.admin))
        .where(School.id == school.id)
    )
    return result.scalar_one()

# ─── Teacher management ───────────────────────────────────────────────────────

@router.get("/teachers", response_model=list[TeacherOut])
async def list_teachers(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_school_admin),
):
    result = await db.execute(select(Teacher).order_by(Teacher.name))
    return result.scalars().all()


@router.post("/teachers", response_model=TeacherOut, status_code=201)
async def create_teacher(
    body: TeacherCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_school_admin),
):
    from app.models.admin import Admin
    from app.models.school_admin import SchoolAdmin
    from app.models.student import Student
    for Model in (Admin, SchoolAdmin, Teacher, Student):
        r = await db.execute(select(Model).where(Model.email == body.email))
        if r.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Email already registered")

    teacher = Teacher(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        profile_image_url=body.profile_image_url,
    )
    db.add(teacher)
    await db.commit()
    await db.refresh(teacher)
    return teacher


# ─── Classes ──────────────────────────────────────────────────────────────────

@router.get("/classes", response_model=list[ClassOut])
async def list_classes(
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    result = await db.execute(
        select(Class).where(Class.school_id == school_admin.school_id).order_by(Class.name)
    )
    return result.scalars().all()


@router.post("/classes", response_model=ClassOut, status_code=201)
async def create_class(
    body: ClassCreate,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    class_ = Class(
        name=body.name,
        profile_image_url=body.profile_image_url,
        school_id=school_admin.school_id,
    )
    db.add(class_)
    await db.commit()
    await db.refresh(class_)
    return class_


@router.get("/classes/{class_id}", response_model=ClassOut)
async def get_class(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    class_ = await _get_owned_class(class_id, school_admin.school_id, db)
    return class_


@router.put("/classes/{class_id}", response_model=ClassOut)
async def update_class(
    class_id: int,
    body: ClassUpdate,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    class_ = await _get_owned_class(class_id, school_admin.school_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(class_, field, value)
    await db.commit()
    await db.refresh(class_)
    return class_


@router.delete("/classes/{class_id}", status_code=204)
async def delete_class(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    class_ = await _get_owned_class(class_id, school_admin.school_id, db)
    await db.delete(class_)
    await db.commit()


# ─── Subjects ─────────────────────────────────────────────────────────────────

@router.get("/classes/{class_id}/subjects", response_model=list[SubjectOut])
async def list_subjects(
    class_id: int,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    await _get_owned_class(class_id, school_admin.school_id, db)
    result = await db.execute(
        select(Subject)
        .options(selectinload(Subject.teacher))
        .where(Subject.class_id == class_id)
        .order_by(Subject.name)
    )
    return result.scalars().all()


@router.post("/classes/{class_id}/subjects", response_model=SubjectOut, status_code=201)
async def create_subject(
    class_id: int,
    body: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    await _get_owned_class(class_id, school_admin.school_id, db)
    subject = Subject(
        name=body.name,
        profile_image_url=body.profile_image_url,
        class_id=class_id,
    )
    db.add(subject)
    await db.commit()

    result = await db.execute(
        select(Subject).options(selectinload(Subject.teacher)).where(Subject.id == subject.id)
    )
    return result.scalar_one()


@router.put("/subjects/{subject_id}", response_model=SubjectOut)
async def update_subject(
    subject_id: int,
    body: SubjectUpdate,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    subject = await _get_owned_subject(subject_id, school_admin.school_id, db)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(subject, field, value)
    await db.commit()

    result = await db.execute(
        select(Subject).options(selectinload(Subject.teacher)).where(Subject.id == subject.id)
    )
    return result.scalar_one()


@router.put("/subjects/{subject_id}/assign-teacher", response_model=SubjectOut)
async def assign_teacher(
    subject_id: int,
    body: AssignTeacherRequest,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    subject = await _get_owned_subject(subject_id, school_admin.school_id, db)

    teacher = await db.get(Teacher, body.teacher_id)
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    subject.teacher_id = body.teacher_id
    await db.commit()

    result = await db.execute(
        select(Subject).options(selectinload(Subject.teacher)).where(Subject.id == subject.id)
    )
    return result.scalar_one()


# ─── Students ────────────────────────────────────────────────────────────────

@router.get("/students", response_model=list[StudentWithClassOut])
async def list_students(
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    result = await db.execute(
        select(Student)
        .options(selectinload(Student.class_))
        .where(Student.school_id == school_admin.school_id)
        .order_by(Student.name)
    )
    students = result.scalars().all()
    return [
        StudentWithClassOut(
            id=s.id,
            name=s.name,
            email=s.email,
            mobile_number=s.mobile_number,
            class_id=s.class_id,
            class_name=s.class_.name,
            created_at=s.created_at,
        )
        for s in students
    ]


@router.get("/subjects/{subject_id}/students", response_model=list[StudentOut])
async def list_subject_students(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    subject = await _get_owned_subject(subject_id, school_admin.school_id, db)
    result = await db.execute(
        select(Student)
        .where(Student.class_id == subject.class_id)
        .order_by(Student.name)
    )
    return result.scalars().all()


# ─── Recordings & Reports (view) ──────────────────────────────────────────────

@router.get("/subjects/{subject_id}/recordings", response_model=list[RecordingWithReport])
async def list_subject_recordings(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    await _get_owned_subject(subject_id, school_admin.school_id, db)
    result = await db.execute(
        select(Recording)
        .options(selectinload(Recording.report))
        .where(Recording.subject_id == subject_id)
        .order_by(Recording.uploaded_at.desc())
    )
    return result.scalars().all()


@router.get("/subjects/{subject_id}/reports", response_model=list[LLMReportOut])
async def list_subject_reports(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    school_admin=Depends(get_school_admin),
):
    await _get_owned_subject(subject_id, school_admin.school_id, db)
    result = await db.execute(
        select(LLMReport)
        .join(Recording, LLMReport.recording_id == Recording.id)
        .where(Recording.subject_id == subject_id)
        .order_by(LLMReport.created_at.desc())
    )
    return result.scalars().all()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_owned_class(class_id: int, school_id: int, db: AsyncSession) -> Class:
    result = await db.execute(select(Class).where(Class.id == class_id))
    class_ = result.scalar_one_or_none()
    if not class_ or class_.school_id != school_id:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_


async def _get_owned_subject(subject_id: int, school_id: int, db: AsyncSession) -> Subject:
    result = await db.execute(
        select(Subject)
        .join(Class, Subject.class_id == Class.id)
        .where(Subject.id == subject_id, Class.school_id == school_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


async def _get_school_admin_with_school(admin_id: int, db: AsyncSession) -> SchoolAdmin:
    result = await db.execute(
        select(SchoolAdmin)
        .options(selectinload(SchoolAdmin.school))
        .where(SchoolAdmin.id == admin_id)
    )
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=404, detail="School admin not found")
    return admin


def _build_school_admin_profile(admin: SchoolAdmin) -> SchoolAdminProfileOut:
    school = admin.school
    return SchoolAdminProfileOut(
        id=admin.id,
        name=admin.name,
        email=admin.email,
        profile_pic_url=admin.profile_pic_url,
        school_id=admin.school_id,
        school_name=school.name,
        school_logo_url=school.logo_url,
        school_address=school.address,
        created_at=admin.created_at,
    )
