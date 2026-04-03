#!/bin/bash
# Start celery worker in the background
celery -A celery_worker.celery_app worker --loglevel=info --concurrency=2 &
# Start uvicorn
uvicorn app.main:app --host 0.0.0.0 --port $PORT
