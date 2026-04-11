# ─────────────────────────────────────────────────────────────
#  app/services/llm.py
#
#  Public API (unchanged — llm_tasks.py keeps working as-is):
#      analyze_recording(cloudinary_url: str) -> dict
#
#  Return shape (same keys as before):
#  {
#      "overall_score":          float,   # pipeline total / 10
#      "teaching_quality_notes": str,
#      "strengths":              str,
#      "improvements":           str,
#      "raw_llm_response":       dict,    # full pipeline output
#  }
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import tempfile

import httpx

from .llm_pipeline import run_pipeline


def _download_audio(url: str) -> str:
    """
    Download an audio file from a Cloudinary URL to a temp file.

    Returns the path to the temp file.
    Caller is responsible for deletion.
    """
    suffix = os.path.splitext(url.split("?")[0])[-1] or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name

    with httpx.Client(follow_redirects=True, timeout=120) as client:
        response = client.get(url)
        response.raise_for_status()
        with open(tmp_path, "wb") as f:
            f.write(response.content)

    return tmp_path


def _format_list(items: list[str]) -> str:
    """Turn a list of strings into a readable bullet string."""
    if not items:
        return "None identified."
    return "\n".join(f"• {item}" for item in items)


def analyze_recording(cloudinary_url: str) -> dict:
    """
    Download a lecture recording from Cloudinary, run it through the
    evaluation pipeline, and return results in the shape that
    llm_tasks.py expects.

    Parameters
    ----------
    cloudinary_url : str
        Public or authenticated Cloudinary URL of the audio file.

    Returns
    -------
    {
        "overall_score":          float,   # 0.0 – 10.0  (pipeline /100 → /10)
        "teaching_quality_notes": str,
        "strengths":              str,     # formatted bullet list
        "improvements":           str,     # formatted bullet list
        "raw_llm_response":       dict,    # complete pipeline output
    }
    """
    tmp_path = _download_audio(cloudinary_url)

    try:
        result = run_pipeline(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ── Map pipeline output → legacy shape ───────────────────
    # pipeline total is 0–100; callers expect a 0–10 float
    overall_score = round(result["total_score"] / 10, 1)

    return {
        "overall_score":          overall_score,
        "teaching_quality_notes": result["teaching_quality_notes"],
        "strengths":              _format_list(result["suggestions"]),
        "improvements":           _format_list(result["issues"]),
        "raw_llm_response":       result,   # full pipeline dict for debugging
    }