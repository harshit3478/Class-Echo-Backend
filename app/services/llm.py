def analyze_recording(cloudinary_url: str) -> dict:
    """
    Mock LLM analysis stub.
    Replace this function body with a real LLM API call when ready.
    Expected return shape must stay the same.
    """
    return {
        "overall_score": 7.5,
        "teaching_quality_notes": (
            "The teacher demonstrated clear explanation of concepts "
            "and maintained student engagement throughout the session."
        ),
        "strengths": (
            "Good pacing, used real-world examples effectively, "
            "encouraged participation."
        ),
        "improvements": (
            "Could ask more open-ended questions to probe student understanding. "
            "Summary at the end of the lecture was brief."
        ),
        "raw_llm_response": {
            "model": "stub",
            "demo": True,
            "input_url": cloudinary_url,
        },
    }
