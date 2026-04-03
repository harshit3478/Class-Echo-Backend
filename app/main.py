from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, admin, school_admin, teacher, student

app = FastAPI(title="ScholarMetric API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(admin.router, prefix="/admin", tags=["Super Admin"])
app.include_router(school_admin.router, prefix="/school", tags=["School Admin"])
app.include_router(teacher.router, prefix="/teacher", tags=["Teacher"])
app.include_router(student.router, prefix="/student", tags=["Student"])


@app.get("/health")
async def health():
    return {"status": "ok"}
