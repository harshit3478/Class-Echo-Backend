# ─────────────────────────────────────────────
#  config.py  –  weights, thresholds, constants
# ─────────────────────────────────────────────

GEMINI_MODEL = "gemini-2.5-flash"

# ── Scoring rubric weights (must sum to 100) ──
SCORE_WEIGHTS: dict[str, int] = {
    "verbal_clarity":          20,
    "pacing_delivery":         15,
    "content_structure":       15,
    "conceptual_depth":        20,
    "student_engagement":      15,
    "language_accessibility":  10,
    "closure_recap":            5,
}

assert sum(SCORE_WEIGHTS.values()) == 100, "Weights must sum to 100"

# ── LLM evaluation prompt (injected with audio file at runtime) ───────────────
EVALUATION_PROMPT_TEMPLATE = """
You are an expert educational evaluator analyzing a lecture recording.

Listen to the complete audio carefully. The lecture may contain Hindi-English code-switching, regional Indian languages, or other multilingual mixing — evaluate the content as-is, understanding all languages present.

## Evaluation Dimensions

Score each dimension strictly and with specific evidence. For every dimension provide:
- A score within the stated maximum
- One precise finding sentence (what you observed, not generic)
- 2–3 short evidence quotes with approximate timestamps (format: "~MM:SS — '...'")

| Dimension                | Max | What to evaluate |
|--------------------------|-----|------------------|
| verbal_clarity           | 20  | Pronunciation, sentence completion, filler words (um/uh/basically/you know), articulation |
| pacing_delivery          | 15  | Speaking rate (words per minute), variation, purposeful pauses, energy and tone |
| content_structure        | 15  | Clear introduction, logical progression, topic transitions, organized flow |
| conceptual_depth         | 20  | Technical accuracy, use of examples/analogies, scaffolding from simple to complex |
| student_engagement       | 15  | Questions directed at students, checks for understanding, wait time, interactive cues |
| language_accessibility   | 10  | Effectiveness of code-switching, jargon explained, all students can follow |
| closure_recap            |  5  | Key points summarized at end, takeaways stated clearly |

## Quantitative Estimates
Estimate from listening to the audio:
- wpm_estimate: approximate words per minute (integer)
- filler_words_heard: total count of filler words heard (um, uh, basically, you know, sort of, etc.)
- questions_asked: number of questions directed at students
- languages_detected: list of language names heard (e.g. ["Hindi", "English"])
- code_switching_frequency: "none" | "low" | "medium" | "high"

## Output Format
Respond ONLY with valid JSON. No markdown fences, no prose outside the object.

{
  "scores": {
    "verbal_clarity":         { "score": <int 0-20>, "finding": "<one specific sentence>", "evidence": ["<~MM:SS — quote>", "<~MM:SS — quote>"] },
    "pacing_delivery":        { "score": <int 0-15>, "finding": "<one specific sentence>", "evidence": ["<~MM:SS — quote>", "<~MM:SS — quote>"] },
    "content_structure":      { "score": <int 0-15>, "finding": "<one specific sentence>", "evidence": ["<~MM:SS — quote>", "<~MM:SS — quote>"] },
    "conceptual_depth":       { "score": <int 0-20>, "finding": "<one specific sentence>", "evidence": ["<~MM:SS — quote>", "<~MM:SS — quote>"] },
    "student_engagement":     { "score": <int 0-15>, "finding": "<one specific sentence>", "evidence": ["<~MM:SS — quote>", "<~MM:SS — quote>"] },
    "language_accessibility": { "score": <int 0-10>, "finding": "<one specific sentence>", "evidence": ["<~MM:SS — quote>", "<~MM:SS — quote>"] },
    "closure_recap":          { "score": <int 0-5>,  "finding": "<one specific sentence>", "evidence": ["<~MM:SS — quote>"] }
  },
  "total": <int 0-100>,
  "quantitative": {
    "wpm_estimate": <int>,
    "filler_words_heard": <int>,
    "questions_asked": <int>,
    "languages_detected": ["<language>"],
    "code_switching_frequency": "<none|low|medium|high>"
  },
  "overall_notes": "<2-3 sentence overall assessment of teaching effectiveness>",
  "top_strengths": ["<specific strength 1>", "<specific strength 2>"],
  "priority_improvements": ["<improvement 1>", "<improvement 2>", "<improvement 3>"]
}
""".strip()
