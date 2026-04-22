from __future__ import annotations

import json
import os
import re
import time

from google import genai
from google.genai import types

from .config import EVALUATION_PROMPT_TEMPLATE, GEMINI_MODEL, SCORE_WEIGHTS

_client: genai.Client | None = None

_MIME_MAP = {
    ".mp3":  "audio/mpeg",
    ".mp4":  "audio/mp4",
    ".m4a":  "audio/mp4",
    ".wav":  "audio/wav",
    ".ogg":  "audio/ogg",
    ".webm": "audio/webm",
    ".aac":  "audio/aac",
    ".flac": "audio/flac",
}


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Export it before running the pipeline."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _mime_type(audio_path: str) -> str:
    ext = os.path.splitext(audio_path)[-1].lower()
    return _MIME_MAP.get(ext, "audio/mpeg")


def _upload_and_wait(client: genai.Client, audio_path: str):
    """Upload audio to Gemini Files API and wait until it is ACTIVE."""
    mime = _mime_type(audio_path)
    uploaded = client.files.upload(
        file=audio_path,
        config={"mime_type": mime, "display_name": "lecture_audio"},
    )
    # Poll until ACTIVE or FAILED (usually a few seconds)
    for _ in range(30):
        f = client.files.get(name=uploaded.name)
        state = f.state.name if hasattr(f.state, "name") else str(f.state)
        if state in ("ACTIVE", "FAILED"):
            if state == "FAILED":
                raise RuntimeError("Gemini Files API failed to process the audio file.")
            return f
        time.sleep(2)
    raise RuntimeError("Timed out waiting for Gemini Files API to process audio.")


def _call_gemini(client: genai.Client, file_ref) -> str:
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_uri(
                file_uri=file_ref.uri,
                mime_type=file_ref.mime_type,
            ),
            EVALUATION_PROMPT_TEMPLATE,
        ],
    )
    return response.text


def _parse_response(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned non-JSON output.\nRaw:\n{raw}\nError: {exc}"
        ) from exc


def _validate_and_fix(result: dict) -> dict:
    scores = result.get("scores", {})
    for dim, max_val in SCORE_WEIGHTS.items():
        if dim not in scores:
            scores[dim] = {"score": 0, "finding": "", "evidence": []}
        entry = scores[dim]
        if isinstance(entry, (int, float)):
            scores[dim] = {"score": max(0, min(int(entry), max_val)), "finding": "", "evidence": []}
        else:
            entry["score"] = max(0, min(int(entry.get("score", 0)), max_val))
            entry["finding"] = str(entry.get("finding", ""))
            entry["evidence"] = [str(e) for e in entry.get("evidence", [])]

    result["scores"] = scores
    result["total"] = sum(v["score"] for v in scores.values())

    quant = result.get("quantitative", {})
    quant.setdefault("wpm_estimate", 0)
    quant.setdefault("filler_words_heard", 0)
    quant.setdefault("questions_asked", 0)
    quant.setdefault("languages_detected", [])
    quant.setdefault("code_switching_frequency", "none")
    result["quantitative"] = quant

    result.setdefault("overall_notes", "")
    result["top_strengths"] = [str(s) for s in result.get("top_strengths", [])]
    result["priority_improvements"] = [str(s) for s in result.get("priority_improvements", [])]

    return result


def evaluate(audio_path: str) -> dict:
    """
    Upload audio_path to Gemini Files API, evaluate the lecture,
    clean up the uploaded file, and return the structured result.
    """
    client = _get_client()
    file_ref = None
    try:
        file_ref = _upload_and_wait(client, audio_path)
        raw = _call_gemini(client, file_ref)
        parsed = _parse_response(raw)
        return _validate_and_fix(parsed)
    finally:
        if file_ref is not None:
            try:
                client.files.delete(name=file_ref.name)
            except Exception:
                pass
