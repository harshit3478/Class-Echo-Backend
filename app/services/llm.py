from __future__ import annotations

import os
import tempfile

import httpx

from .llm_pipeline import run_pipeline


def _download_audio(url: str) -> str:
    suffix = os.path.splitext(url.split("?")[0])[-1] or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        r = client.get(url)
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            f.write(r.content)
    return tmp_path


def analyze_recording(cloudinary_url: str) -> dict:
    """
    Download a lecture recording from Cloudinary, evaluate with Gemini audio,
    and return results shaped for LLMReport storage.

    Returns
    -------
    {
        "overall_score":          int (0-100),
        "teaching_quality_notes": str,
        "score_breakdown":        dict,  per-dimension {score, finding, evidence}
        "quantitative_metrics":   dict,  wpm, fillers, questions, languages, strengths, improvements
        "raw_llm_response":       dict,
    }
    """
    tmp_path = _download_audio(cloudinary_url)
    try:
        result = run_pipeline(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return {
        "overall_score":          result["total"],
        "teaching_quality_notes": result["overall_notes"],
        "score_breakdown":        result["scores"],
        "quantitative_metrics": {
            **result["quantitative"],
            "top_strengths":         result["top_strengths"],
            "priority_improvements": result["priority_improvements"],
        },
        "raw_llm_response": result,
    }
