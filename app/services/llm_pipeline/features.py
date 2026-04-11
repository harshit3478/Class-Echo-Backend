# ─────────────────────────────────────────────────────────────
#  features.py  –  deterministic feature extraction
#
#  Two entry points
#  ─────────────────
#  extract_audio_features(audio_path)   → dict   (needs waveform)
#  extract_text_features(transcript)    → dict   (needs transcript dict)
#  extract_all(audio_path, transcript)  → dict   (combines both)
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import re
import statistics
from typing import Any

import librosa
import numpy as np

from .config import IDEAL_WPM_MAX, IDEAL_WPM_MIN, SAMPLE_RATE

# ─────────────────────────────────────────────────────────────
#  AUDIO FEATURES  (operate on the waveform)
# ─────────────────────────────────────────────────────────────

def _signal_to_noise_ratio(samples: np.ndarray) -> float:
    """Estimate SNR in dB using mean / std of the signal."""
    signal_power = np.mean(samples ** 2)
    noise_power  = np.var(samples)
    if noise_power == 0:
        return float("inf")
    return float(10 * np.log10(signal_power / noise_power))


def _volume_variance(samples: np.ndarray, sr: int) -> float:
    """
    RMS energy variance across 1-second frames.
    High variance → dynamic / expressive delivery.
    Low variance  → monotone delivery.
    """
    frame_len = sr  # 1-second frames
    rms_values = [
        float(np.sqrt(np.mean(samples[i : i + frame_len] ** 2)))
        for i in range(0, len(samples) - frame_len, frame_len)
    ]
    return statistics.variance(rms_values) if len(rms_values) > 1 else 0.0


def extract_audio_features(audio_path: str) -> dict[str, Any]:
    """
    Compute waveform-level audio quality metrics.

    Returns
    -------
    {
        "snr_db":          float,  # signal-to-noise ratio
        "volume_variance": float,  # dynamic range proxy
        "duration_seconds":float,
    }
    """
    samples, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)

    return {
        "snr_db":           _signal_to_noise_ratio(samples),
        "volume_variance":  _volume_variance(samples, sr),
        "duration_seconds": float(len(samples) / sr),
    }


# ─────────────────────────────────────────────────────────────
#  TEXT FEATURES  (operate on the transcript dict)
# ─────────────────────────────────────────────────────────────

# ── helpers ──────────────────────────────────────────────────

_QUESTION_PATTERN = re.compile(
    r"(any (questions|doubts|queries)|do you understand|"
    r"can anyone|what (do|did|is|are|was|were)|how (do|does|did|is)|"
    r"why (is|are|do|did|was|were)|\?)",
    re.IGNORECASE,
)

_EXAMPLE_PATTERN = re.compile(
    r"\b(for example|for instance|e\.g\.|such as|like|consider|"
    r"let'?s? (take|look at|say))\b",
    re.IGNORECASE,
)

_ANALOGY_PATTERN = re.compile(
    r"\b(similar(ly)?|just like|analogous|think of .{0,30} as|"
    r"imagine|picture this|it'?s? (like|similar to))\b",
    re.IGNORECASE,
)

_SUMMARY_PHRASES = re.compile(
    r"\b(to summarize|to sum up|in summary|in conclusion|"
    r"so today we (learned|covered|discussed)|"
    r"the key (points?|takeaways?) (are|is|were))\b",
    re.IGNORECASE,
)

_FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|er+|ah+|like|you know|basically|literally|"
    r"sort of|kind of|right\?|okay\?)\b",
    re.IGNORECASE,
)


# ── pace ─────────────────────────────────────────────────────

def _pace_features(segments: list[dict]) -> dict[str, Any]:
    """
    Words per minute and pause statistics derived from Whisper segments.
    """
    if not segments:
        return {"wpm": 0.0, "avg_pause_seconds": 0.0, "wpm_in_ideal_range": False}

    total_words    = sum(len(s["text"].split()) for s in segments)
    total_duration = segments[-1]["end"] - segments[0]["start"]
    wpm = (total_words / total_duration * 60) if total_duration > 0 else 0.0

    # Pauses = gaps between consecutive segments
    pauses = [
        segments[i + 1]["start"] - segments[i]["end"]
        for i in range(len(segments) - 1)
        if segments[i + 1]["start"] - segments[i]["end"] > 0.1  # ignore micro-gaps
    ]
    avg_pause = statistics.mean(pauses) if pauses else 0.0

    return {
        "wpm":                 round(wpm, 1),
        "avg_pause_seconds":   round(avg_pause, 2),
        "wpm_in_ideal_range":  IDEAL_WPM_MIN <= wpm <= IDEAL_WPM_MAX,
    }


# ── structure ────────────────────────────────────────────────

def _structure_features(full_text: str, segments: list[dict]) -> dict[str, Any]:
    """
    Rough structural analysis: word count, estimated section count,
    and a heuristic transition score.
    """
    words      = full_text.split()
    word_count = len(words)

    # Chunk transcript into ~200-word windows and count semantic "turns"
    # (a simple proxy for topic transitions without heavy NLP deps)
    transition_keywords = re.compile(
        r"\b(now|next|moving on|let'?s? (now|talk|discuss|look)|"
        r"another|additionally|furthermore|however|in contrast|"
        r"on the other hand|finally|lastly)\b",
        re.IGNORECASE,
    )
    transitions = len(transition_keywords.findall(full_text))
    # Normalise: ~1 transition per 150 words is considered well-structured
    expected_transitions = max(1, word_count / 150)
    transition_score = min(1.0, transitions / expected_transitions)

    return {
        "word_count":       word_count,
        "segment_count":    len(segments),
        "transition_count": transitions,
        "transition_score": round(transition_score, 3),
    }


# ── interaction ───────────────────────────────────────────────

def _interaction_features(full_text: str) -> dict[str, Any]:
    questions       = _QUESTION_PATTERN.findall(full_text)
    filler_words    = _FILLER_PATTERN.findall(full_text)
    word_count      = max(1, len(full_text.split()))
    filler_rate     = len(filler_words) / word_count

    return {
        "question_count":  len(questions),
        "filler_count":    len(filler_words),
        "filler_rate":     round(filler_rate, 4),
    }


# ── pedagogy ─────────────────────────────────────────────────

def _pedagogy_features(full_text: str) -> dict[str, Any]:
    examples  = _EXAMPLE_PATTERN.findall(full_text)
    analogies = _ANALOGY_PATTERN.findall(full_text)

    # Repetition: words that appear ≥ 3× (excluding stopwords) as key-concept proxy
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "to", "of",
        "and", "in", "it", "that", "this", "i", "you", "we",
    }
    word_freq: dict[str, int] = {}
    for word in re.findall(r"\b[a-z]{4,}\b", full_text.lower()):
        if word not in stopwords:
            word_freq[word] = word_freq.get(word, 0) + 1
    repeated_concepts = [w for w, c in word_freq.items() if c >= 3]

    return {
        "example_count":         len(examples),
        "analogy_count":         len(analogies),
        "repeated_concept_count": len(repeated_concepts),
    }


# ── summary detection ────────────────────────────────────────

def _summary_features(full_text: str, segments: list[dict]) -> dict[str, Any]:
    """
    Check whether the last 15 % of the lecture contains a summary.
    """
    if not segments:
        return {"has_summary": False, "summary_phrases_found": 0}

    total_duration   = segments[-1]["end"] - segments[0]["start"]
    summary_start_t  = segments[0]["start"] + total_duration * 0.85

    tail_text = " ".join(
        s["text"] for s in segments if s["start"] >= summary_start_t
    )
    matches = _SUMMARY_PHRASES.findall(tail_text)

    return {
        "has_summary":          len(matches) > 0,
        "summary_phrases_found": len(matches),
    }


# ─────────────────────────────────────────────────────────────
#  Combined entry point
# ─────────────────────────────────────────────────────────────

def extract_text_features(transcript: dict) -> dict[str, Any]:
    """
    Run all text-based feature extractors on a transcript dict.

    Parameters
    ----------
    transcript : dict with keys "full_text" and "segments"

    Returns
    -------
    {
        "pace":        { … },
        "structure":   { … },
        "interaction": { … },
        "pedagogy":    { … },
        "summary":     { … },
    }
    """
    full_text = transcript.get("full_text", "")
    segments  = transcript.get("segments", [])

    return {
        "pace":        _pace_features(segments),
        "structure":   _structure_features(full_text, segments),
        "interaction": _interaction_features(full_text),
        "pedagogy":    _pedagogy_features(full_text),
        "summary":     _summary_features(full_text, segments),
    }


def extract_all(audio_path: str, transcript: dict) -> dict[str, Any]:
    """
    Convenience function: audio features + text features in one dict.

    Returns
    -------
    {
        "audio":       { snr_db, volume_variance, duration_seconds },
        "pace":        { … },
        "structure":   { … },
        "interaction": { … },
        "pedagogy":    { … },
        "summary":     { … },
    }
    """
    audio_feats = extract_audio_features(audio_path)
    text_feats  = extract_text_features(transcript)
    return {"audio": audio_feats, **text_feats}