# ─────────────────────────────────────────────────────────────
#  audio_processing.py  –  clean audio, then transcribe it
#
#  Input : path to any audio file (mp3, wav, m4a, …)
#  Output: {
#              "full_text": str,
#              "segments": [{"start": float, "end": float, "text": str}, …]
#          }
# ─────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import tempfile

from faster_whisper import WhisperModel
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

from .config import (
    MIN_SILENCE_LEN_MS,
    SAMPLE_RATE,
    SILENCE_THRESHOLD,
    WHISPER_MODEL_SIZE,
)

# ── Lazy-load Whisper so the model is downloaded only once ────
_whisper_model: WhisperModel | None = None


def _get_whisper() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _whisper_model


# ─────────────────────────────────────────────────────────────
#  1. Preprocessing
# ─────────────────────────────────────────────────────────────

def _normalize_volume(audio: AudioSegment) -> AudioSegment:
    """Bring average loudness to a consistent level."""
    target_dBFS = -20.0
    change = target_dBFS - audio.dBFS
    return audio.apply_gain(change)


def _trim_silence(audio: AudioSegment) -> AudioSegment:
    """Remove leading/trailing silence and join non-silent chunks."""
    chunks = detect_nonsilent(
        audio,
        min_silence_len=MIN_SILENCE_LEN_MS,
        silence_thresh=SILENCE_THRESHOLD,
    )
    if not chunks:
        return audio  # entire clip is silence — return as-is
    start_ms, end_ms = chunks[0][0], chunks[-1][1]
    return audio[start_ms:end_ms]


def preprocess(audio_path: str) -> str:
    """
    Clean an audio file and write the result to a temp WAV file.

    Steps
    -----
    1. Load with pydub (handles mp3 / m4a / wav / …)
    2. Normalise volume
    3. Trim silence
    4. Convert to mono 16 kHz (Whisper's expected format)
    5. Write to a temporary WAV file

    Returns
    -------
    Path to the cleaned WAV file (caller is responsible for deletion).
    """
    audio = AudioSegment.from_file(audio_path)
    audio = _normalize_volume(audio)
    audio = _trim_silence(audio)
    audio = audio.set_channels(1).set_frame_rate(SAMPLE_RATE)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name
    audio.export(tmp_wav, format="wav")
    return tmp_wav


# ─────────────────────────────────────────────────────────────
#  2. Transcription
# ─────────────────────────────────────────────────────────────

def transcribe(cleaned_wav: str) -> dict:
    """
    Run Whisper on a cleaned WAV file.

    Returns
    -------
    {
        "full_text": "<entire transcript as one string>",
        "segments":  [{"start": float, "end": float, "text": str}, …]
    }
    """
    model = _get_whisper()
    # faster-whisper returns a generator of Segment objects + TranscriptionInfo
    seg_iter, _ = model.transcribe(cleaned_wav, language="en")

    segments = []
    texts: list[str] = []
    for seg in seg_iter:
        text = seg.text.strip()
        segments.append({"start": seg.start, "end": seg.end, "text": text})
        texts.append(text)

    return {
        "full_text": " ".join(texts),
        "segments":  segments,
    }


# ─────────────────────────────────────────────────────────────
#  3. Combined entry point
# ─────────────────────────────────────────────────────────────

def process_audio(audio_path: str) -> dict:
    """
    Preprocess + transcribe in one call.

    Cleans up the temporary WAV file before returning.

    Returns
    -------
    Transcript dict — see `transcribe()` for shape.
    """
    cleaned_wav = preprocess(audio_path)
    try:
        return transcribe(cleaned_wav)
    finally:
        if os.path.exists(cleaned_wav):
            os.remove(cleaned_wav)