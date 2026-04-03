"""
Run this script to create all database tables.

Use this instead of 'alembic upgrade head' if your DATABASE_URL
points to Neon's connection pooler endpoint (the one with -pooler in the hostname).
The pooler uses PgBouncer which doesn't support DDL transactions, causing
Alembic to stamp migrations as applied without actually creating tables.

This script uses asyncpg directly, which handles Neon SSL correctly.

Usage:
    python create_tables.py
"""
import asyncio

import app.models  # noqa: F401 — registers all models
from app.database import Base, engine


async def main():
    print("Connecting to database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Done. Tables created (existing tables were skipped):")
    for table in sorted(Base.metadata.tables.keys()):
        print(f"  ✓ {table}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
