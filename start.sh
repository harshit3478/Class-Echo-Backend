#!/bin/bash
# Run database migrations
alembic upgrade head

# Seed the database
python seed_admin.py

# Start celery worker in the background
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=1 &
# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
