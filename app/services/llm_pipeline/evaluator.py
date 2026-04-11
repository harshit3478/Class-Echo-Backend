# ─────────────────────────────────────────────────────────────
#  evaluator.py  –  single Gemini call → scores + feedback
#
#  Input : transcript dict + features dict
#  Output: {
#              "scores":                 { clarity, delivery, … },
#              "total":                  int,
#              "issues":                 [str, …],
#              "suggestions":            [str, …],
#              "teaching_quality_notes": str,
#          }
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import os
import re

import google.generativeai as genai

from .config import (
    EVALUATION_PROMPT_TEMPLATE,
    GEMINI_MODEL,
    IDEAL_WPM_MAX,
    IDEAL_WPM_MIN,
    SCORE_WEIGHTS,
)

# ── Initialise Gemini (reads GEMINI_API_KEY from environment) ─
_client_initialised = False


def _ensure_client() -> None:
    global _client_initialised
    if not _client_initialised:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Export it before running the pipeline."
            )
        genai.configure(api_key=api_key)
        _client_initialised = True


# ─────────────────────────────────────────────────────────────
#  Prompt building
# ─────────────────────────────────────────────────────────────

def _build_prompt(transcript: dict, features: dict) -> str:
    """Fill the prompt template with real data."""
    return EVALUATION_PROMPT_TEMPLATE.format(
        transcript=transcript.get("full_text", ""),
        features=json.dumps(features, indent=2),
        wpm_min=IDEAL_WPM_MIN,
        wpm_max=IDEAL_WPM_MAX,
    )


# ─────────────────────────────────────────────────────────────
#  Gemini call
# ─────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    """Send a prompt to Gemini and return the raw text response."""
    _ensure_client()
    model    = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text


def _parse_response(raw: str) -> dict:
    """
    Extract a JSON object from the model response.

    Gemini sometimes wraps JSON in markdown fences; this strips them.
    """
    # Remove ```json … ``` fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Gemini returned non-JSON output.\n"
            f"Raw response:\n{raw}\n\nParse error: {exc}"
        ) from exc


# ─────────────────────────────────────────────────────────────
#  Validation & fallback
# ─────────────────────────────────────────────────────────────

def _validate_and_fix(result: dict) -> dict:
    """
    Ensure the parsed dict has all required keys and valid score ranges.
    Missing keys are filled with safe defaults so the pipeline never crashes.
    """
    # Scores
    scores = result.get("scores", {})
    for dim, max_val in SCORE_WEIGHTS.items():
        if dim not in scores or not isinstance(scores[dim], (int, float)):
            scores[dim] = 0
        scores[dim] = max(0, min(int(scores[dim]), max_val))
    result["scores"] = scores

    # Total — recalculate from individual scores to guard against LLM arithmetic
    result["total"] = sum(scores.values())

    # Lists
    result.setdefault("issues", [])
    result.setdefault("suggestions", [])
    result.setdefault("teaching_quality_notes", "")

    # Ensure lists contain strings
    result["issues"]      = [str(i) for i in result["issues"]]
    result["suggestions"] = [str(s) for s in result["suggestions"]]

    return result


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────

def evaluate(transcript: dict, features: dict) -> dict:
    """
    Call Gemini once with transcript + features and return a validated
    evaluation result.

    Parameters
    ----------
    transcript : dict
        Output of audio_processing.process_audio()
        Keys: "full_text", "segments"

    features : dict
        Output of features.extract_all()
        Keys: "audio", "pace", "structure", "interaction", "pedagogy", "summary"

    Returns
    -------
    {
        "scores": {
            "clarity":     int,   # 0–25
            "delivery":    int,   # 0–15
            "pace":        int,   # 0–15
            "interaction": int,   # 0–20
            "pedagogy":    int,   # 0–15
            "summary":     int,   # 0–10
        },
        "total":                  int,   # 0–100
        "issues":                 list[str],
        "suggestions":            list[str],
        "teaching_quality_notes": str,
    }
    """
    prompt = _build_prompt(transcript, features)
    raw    = _call_gemini(prompt)
    parsed = _parse_response(raw)
    return _validate_and_fix(parsed)