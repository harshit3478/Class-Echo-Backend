# ─────────────────────────────────────────────────────────────
#  pipeline.py  –  end-to-end orchestrator
#
#  Single public function:
#      run_pipeline(audio_path) -> dict
#
#  Output shape
#  ────────────
#  {
#      "total_score":  int,           # 0–100
#      "breakdown": {                 # per-dimension scores
#          "clarity":     int,
#          "delivery":    int,
#          "pace":        int,
#          "interaction": int,
#          "pedagogy":    int,
#          "summary":     int,
#      },
#      "issues":      [str, …],       # problems observed
#      "suggestions": [str, …],       # actionable improvements
#      "teaching_quality_notes": str, # qualitative summary
#      "meta": {
#          "duration_seconds": float,
#          "word_count":       int,
#          "wpm":              float,
#          "snr_db":           float,
#      }
#  }
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import logging

from .audio_processing import process_audio
from .evaluator import evaluate
from .features import extract_all

logger = logging.getLogger(__name__)


def run_pipeline(audio_path: str) -> dict:
    """
    Run the full lecture evaluation pipeline.

    Parameters
    ----------
    audio_path : str
        Absolute or relative path to the lecture audio file.
        Supported formats: mp3, wav, m4a, ogg, flac (anything pydub handles).

    Returns
    -------
    dict
        See module docstring for the full output shape.

    Raises
    ------
    FileNotFoundError
        If `audio_path` does not exist.
    EnvironmentError
        If GEMINI_API_KEY is not set.
    ValueError
        If Gemini returns unparseable output (should be rare).
    """
    import os
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # ── Step 1: Preprocess + transcribe ──────────────────────
    logger.info("Step 1/3 — audio processing: %s", audio_path)
    transcript = process_audio(audio_path)
    logger.info(
        "Transcription complete — %d words, %d segments",
        len(transcript["full_text"].split()),
        len(transcript["segments"]),
    )

    # ── Step 2: Feature extraction ───────────────────────────
    logger.info("Step 2/3 — feature extraction")
    features = extract_all(audio_path, transcript)
    logger.info(
        "Features extracted — WPM: %.1f, questions: %d, examples: %d",
        features["pace"]["wpm"],
        features["interaction"]["question_count"],
        features["pedagogy"]["example_count"],
    )

    # ── Step 3: LLM evaluation ───────────────────────────────
    logger.info("Step 3/3 — LLM evaluation via Gemini")
    evaluation = evaluate(transcript, features)
    logger.info("Evaluation complete — total score: %d/100", evaluation["total"])

    # ── Assemble final output ─────────────────────────────────
    return {
        "total_score": evaluation["total"],
        "breakdown":   evaluation["scores"],
        "issues":      evaluation["issues"],
        "suggestions": evaluation["suggestions"],
        "teaching_quality_notes": evaluation["teaching_quality_notes"],
        "meta": {
            "duration_seconds": features["audio"]["duration_seconds"],
            "word_count":       features["structure"]["word_count"],
            "wpm":              features["pace"]["wpm"],
            "snr_db":           features["audio"]["snr_db"],
        },
    }