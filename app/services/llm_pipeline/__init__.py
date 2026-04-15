"""
llm_pipeline
============
Lecture evaluation pipeline.

Typical usage
-------------
    from app.services.llm_pipeline import run_pipeline

    result = run_pipeline("/path/to/lecture.mp3")
    print(result["total_score"])   # e.g. 78
"""

from .pipeline import run_pipeline

__all__ = ["run_pipeline"]