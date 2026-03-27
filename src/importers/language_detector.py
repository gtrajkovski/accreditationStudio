"""Language detection for documents.

Detects primary language of text:
- EN: English
- ES: Spanish
- BILINGUAL: Mixed English/Spanish content

Phase 29: AI-enhanced detection using Haiku for improved accuracy.
"""

import re
import json
from typing import Dict, Any, Optional


# Language indicator word lists
SPANISH_INDICATORS = [
    "el", "la", "de", "que", "en", "los", "del", "las", "un", "por",
    "con", "para", "una", "su", "al", "es", "lo", "como", "más", "pero",
    "está", "son", "este", "esta", "estos", "estas", "ser", "tiene",
    "pueden", "año", "años", "sobre", "entre", "cuando", "muy", "sin",
    "me", "ya", "porque", "hasta", "donde", "quien", "desde", "durante",
    "también", "sólo", "hay", "fue", "era", "hacer", "otros", "cada",
]

ENGLISH_INDICATORS = [
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    "or", "an", "will", "my", "one", "all", "would", "there", "their",
    "what", "so", "up", "out", "if", "about", "who", "get", "which", "go",
]


def detect_language_simple(text: str) -> Dict[str, Any]:
    """Detect language using word-list method (fast, free).

    Args:
        text: Text sample to analyze (recommended 500+ chars)

    Returns:
        Dict with language, confidence, and ratios
    """
    # Tokenize and lowercase
    words = re.findall(r'\b[a-záéíóúñü]+\b', text.lower())

    if len(words) < 10:
        return {
            "language": "en",
            "confidence": 0.5,
            "note": "Too few words to analyze reliably",
            "method": "simple"
        }

    # Count indicator words
    english_count = sum(1 for w in words if w in ENGLISH_INDICATORS)
    spanish_count = sum(1 for w in words if w in SPANISH_INDICATORS)

    total_indicators = english_count + spanish_count
    if total_indicators == 0:
        return {
            "language": "en",
            "confidence": 0.5,
            "note": "No language indicators found, defaulting to English",
            "method": "simple"
        }

    english_ratio = english_count / total_indicators
    spanish_ratio = spanish_count / total_indicators

    if english_ratio > 0.8:
        return {
            "language": "en",
            "confidence": min(0.5 + english_ratio * 0.5, 0.95),
            "english_ratio": round(english_ratio, 2),
            "spanish_ratio": round(spanish_ratio, 2),
            "method": "simple"
        }
    elif spanish_ratio > 0.8:
        return {
            "language": "es",
            "confidence": min(0.5 + spanish_ratio * 0.5, 0.95),
            "english_ratio": round(english_ratio, 2),
            "spanish_ratio": round(spanish_ratio, 2),
            "method": "simple"
        }
    else:
        return {
            "language": "bilingual",
            "confidence": 0.85,
            "english_ratio": round(english_ratio, 2),
            "spanish_ratio": round(spanish_ratio, 2),
            "method": "simple"
        }


def detect_language_ai(text: str, ai_client) -> Dict[str, Any]:
    """Detect language using AI (routed to Haiku for cost efficiency).

    Uses Claude Haiku for more accurate language detection, especially
    for mixed-language documents and edge cases.

    Args:
        text: Text sample to analyze (limited to 2000 chars for efficiency)
        ai_client: AIClient instance

    Returns:
        Dict with language, confidence, and detected characteristics
    """
    # Limit input for cost efficiency
    text_sample = text[:2000]

    # System prompt for language detection
    system_prompt = """You are a language detection specialist for educational documents.

Your task is to identify the primary language of text. Output ONLY valid JSON.

Languages to detect:
- en: English (>80% English content)
- es: Spanish (>80% Spanish content)
- bilingual: Mixed English/Spanish (20-80% each)

Output format (JSON only, no other text):
{
  "language": "en",
  "confidence": 0.95,
  "english_ratio": 0.9,
  "spanish_ratio": 0.1,
  "notes": "Primarily English with minimal Spanish terms"
}

Analyze word choice, grammar patterns, and overall document structure."""

    user_prompt = f"Detect the primary language of this text:\n\n{text_sample}"

    try:
        # Use fast model - simple classification task (Phase 29)
        response = ai_client.generate_fast(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        # Parse JSON response
        result = json.loads(response.strip())
        result["method"] = "ai"
        return result

    except (json.JSONDecodeError, Exception):
        # Fallback to simple detection on AI failure
        return detect_language_simple(text_sample)


def detect_language_hybrid(text: str, ai_client: Optional[object] = None) -> Dict[str, Any]:
    """Hybrid language detection combining word-list + AI (Phase 29).

    Uses word-list method first (fast, free). Falls back to AI for
    uncertain cases or when confidence is low.

    Routes AI calls to Haiku for 90% cost savings.

    Args:
        text: Text sample to analyze
        ai_client: Optional AIClient instance for AI-enhanced detection

    Returns:
        Dict with language, confidence, ratios, and method used
    """
    # Start with simple detection
    simple_result = detect_language_simple(text)

    # If no AI client or high confidence, use simple result
    if not ai_client or simple_result.get("confidence", 0) > 0.85:
        return simple_result

    # If confidence is low or text is short, use AI enhancement
    if simple_result.get("confidence", 0) < 0.7 or len(text) < 200:
        return detect_language_ai(text, ai_client)

    return simple_result


def detect_language(text: str) -> str:
    """Convenience function to detect language (simple method).

    Args:
        text: Text sample to analyze

    Returns:
        Language code: "en", "es", or "bilingual"
    """
    result = detect_language_simple(text)
    return result.get("language", "en")
