from __future__ import annotations

import logging
import os

from .evaluator import evaluate

logger = logging.getLogger(__name__)


def run_pipeline(audio_path: str) -> dict:
    """
    Evaluate a lecture audio file using Gemini's native audio processing.

    Steps: upload to Gemini Files API → single evaluation call → return result.

    Returns
    -------
    {
        "total":   int (0-100),
        "scores":  { dim: { score, finding, evidence } },
        "quantitative": { wpm_estimate, filler_words_heard, questions_asked,
                          languages_detected, code_switching_frequency },
        "overall_notes":         str,
        "top_strengths":         [str],
        "priority_improvements": [str],
    }
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    logger.info("Uploading audio to Gemini Files API: %s", audio_path)
    result = evaluate(audio_path)
    logger.info("Evaluation complete — total score: %d/100", result["total"])
    return result
