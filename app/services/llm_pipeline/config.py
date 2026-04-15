# ─────────────────────────────────────────────
#  config.py  –  weights, thresholds, constants
# ─────────────────────────────────────────────

# ── Gemini model ──────────────────────────────
GEMINI_MODEL = "gemini-2.0-flash"

# ── Audio preprocessing ───────────────────────
SAMPLE_RATE        = 16_000   # Hz  (Whisper expects 16 kHz)
SILENCE_THRESHOLD  = 40       # dBFS  — frames quieter than this are silence
MIN_SILENCE_LEN_MS = 500      # ms   — minimum silence duration to trim

# ── Whisper ───────────────────────────────────
WHISPER_MODEL_SIZE = "base"   # tiny | base | small | medium | large

# ── Pace analysis ─────────────────────────────
IDEAL_WPM_MIN = 120
IDEAL_WPM_MAX = 160

# ── Scoring rubric weights (must sum to 100) ──
SCORE_WEIGHTS: dict[str, int] = {
    "clarity":     25,
    "delivery":    15,
    "pace":        15,
    "interaction": 20,
    "pedagogy":    15,
    "summary":     10,
}

assert sum(SCORE_WEIGHTS.values()) == 100, "Weights must sum to 100"

# ── LLM evaluation prompt ─────────────────────
# {transcript} and {features} are injected at runtime by evaluator.py
EVALUATION_PROMPT_TEMPLATE = """
You are an expert educational coach evaluating a recorded lecture.

## Transcript
{transcript}

## Extracted Features
{features}

## Scoring Rubric
Score each dimension out of its maximum. Be strict and evidence-based.

| Dimension   | Max | What to look for |
|-------------|-----|------------------|
| clarity     | 25  | Logical flow, absence of jargon, coherent explanations |
| delivery    | 15  | Confidence, tone variety, absence of excessive fillers |
| pace        | 15  | Words-per-minute in range {wpm_min}–{wpm_max}, balanced pauses |
| interaction | 20  | Questions posed, student engagement cues, real-time checks |
| pedagogy    | 15  | Examples, analogies, repetition of key concepts |
| summary     | 10  | Recap of key points at or near the end of the lecture |

## Output Format
Respond ONLY with valid JSON — no markdown, no prose outside the object.

{{
  "scores": {{
    "clarity":     <int 0–25>,
    "delivery":    <int 0–15>,
    "pace":        <int 0–15>,
    "interaction": <int 0–20>,
    "pedagogy":    <int 0–15>,
    "summary":     <int 0–10>
  }},
  "total": <int 0–100>,
  "issues": [
    "<concise description of a problem observed>"
  ],
  "suggestions": [
    "<actionable improvement suggestion>"
  ],
  "teaching_quality_notes": "<2–4 sentence overall qualitative assessment>"
}}
""".strip()