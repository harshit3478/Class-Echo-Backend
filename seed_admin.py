"""
Seed the first Super Admin into the database.

Reads credentials from .env (ADMIN_NAME, ADMIN_EMAIL, ADMIN_PASSWORD).
Safe to run multiple times — skips creation if the email already exists.

Usage:
    python seed_admin.py
"""
import asyncio
import os

from dotenv import load_dotenv
from sqlalchemy import select

load_dotenv()

import app.models  # noqa: F401 — register all models
from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models.admin import Admin


async def main():
    name = os.environ.get("ADMIN_NAME", "Super Admin")
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")

    if not email or not password:
        print("ERROR: Set ADMIN_EMAIL and ADMIN_PASSWORD in your .env file first.")
        return

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(Admin).where(Admin.email == email))
        if existing.scalar_one_or_none():
            print(f"Admin '{email}' already exists — nothing created.")
            return

        admin = Admin(
            name=name,
            email=email,
            hashed_password=hash_password(password),
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)

    print(f"Super admin created: {admin.name} <{admin.email}>")
    print("Log in via POST /auth/login")


if __name__ == "__main__":
    asyncio.run(main())
