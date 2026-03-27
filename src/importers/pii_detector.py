"""PII (Personally Identifiable Information) detection and redaction.

Detects common PII patterns:
- Social Security Numbers (SSN)
- Phone numbers
- Email addresses
- Dates of birth
- Street addresses
- Credit card numbers

Phase 29: Added AI-enhanced detection using Haiku for edge cases.
"""

import re
import json
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class PIIMatch:
    """A detected PII instance."""
    pii_type: str
    value: str
    start: int
    end: int
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pii_type": self.pii_type,
            "value": self.value,
            "start": self.start,
            "end": self.end,
            "confidence": self.confidence,
        }


class PIIDetector:
    """Detect and redact PII from text."""

    # PII patterns with named groups
    PATTERNS = {
        "ssn": (
            r'\b(\d{3}[-.\s]?\d{2}[-.\s]?\d{4})\b',
            "Social Security Number"
        ),
        "phone": (
            r'\b(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b',
            "Phone Number"
        ),
        "email": (
            r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b',
            "Email Address"
        ),
        "dob": (
            r'\b((?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2})\b',
            "Date of Birth"
        ),
        "credit_card": (
            r'\b(\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4})\b',
            "Credit Card Number"
        ),
        "zip_code": (
            r'\b(\d{5}(?:-\d{4})?)\b',
            "ZIP Code"
        ),
    }

    # Redaction placeholder format
    REDACTION_FORMAT = "[REDACTED:{type}]"

    def __init__(self, enabled_types: List[str] = None):
        """Initialize detector with optional type filter.

        Args:
            enabled_types: List of PII types to detect. None = all types.
        """
        if enabled_types:
            self.patterns = {
                k: v for k, v in self.PATTERNS.items()
                if k in enabled_types
            }
        else:
            self.patterns = self.PATTERNS.copy()

    def detect(self, text: str) -> List[PIIMatch]:
        """Detect PII in text.

        Args:
            text: Text to scan for PII.

        Returns:
            List of PIIMatch objects.
        """
        matches = []

        for pii_type, (pattern, _) in self.patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = match.group(1)

                # Validate specific types
                if pii_type == "ssn" and not self._validate_ssn(value):
                    continue
                if pii_type == "credit_card" and not self._validate_credit_card(value):
                    continue

                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=value,
                    start=match.start(1),
                    end=match.end(1),
                    confidence=self._calculate_confidence(pii_type, value),
                ))

        # Sort by position
        matches.sort(key=lambda m: m.start)

        return matches

    def redact(self, text: str, matches: List[PIIMatch] = None) -> Tuple[str, List[PIIMatch]]:
        """Redact PII from text.

        Args:
            text: Text to redact.
            matches: Optional pre-detected matches. If None, detect first.

        Returns:
            Tuple of (redacted_text, matches).
        """
        if matches is None:
            matches = self.detect(text)

        if not matches:
            return text, []

        # Build redacted text (work backwards to preserve positions)
        result = text
        for match in reversed(matches):
            placeholder = self.REDACTION_FORMAT.format(type=match.pii_type.upper())
            result = result[:match.start] + placeholder + result[match.end:]

        return result, matches

    def detect_and_redact(self, text: str) -> Dict[str, Any]:
        """Detect and redact PII, returning full report.

        Args:
            text: Text to process.

        Returns:
            Dict with redacted_text, matches, and summary.
        """
        matches = self.detect(text)
        redacted, _ = self.redact(text, matches)

        # Summary by type
        summary = {}
        for match in matches:
            pii_type = match.pii_type
            if pii_type not in summary:
                summary[pii_type] = {"count": 0, "label": self.PATTERNS[pii_type][1]}
            summary[pii_type]["count"] += 1

        return {
            "original_length": len(text),
            "redacted_text": redacted,
            "redacted_length": len(redacted),
            "pii_found": len(matches) > 0,
            "pii_count": len(matches),
            "pii_matches": [m.to_dict() for m in matches],
            "pii_summary": summary,
        }

    def _validate_ssn(self, value: str) -> bool:
        """Validate SSN format (basic check)."""
        # Remove separators
        digits = re.sub(r'[-.\s]', '', value)
        if len(digits) != 9:
            return False
        # SSN can't start with 9, 666, or 000
        if digits.startswith('9') or digits.startswith('666') or digits.startswith('000'):
            return False
        # Middle and last parts can't be all zeros
        if digits[3:5] == '00' or digits[5:] == '0000':
            return False
        return True

    def _validate_credit_card(self, value: str) -> bool:
        """Validate credit card using Luhn algorithm."""
        digits = re.sub(r'[-.\s]', '', value)
        if len(digits) not in (15, 16):
            return False

        # Luhn algorithm
        total = 0
        for i, digit in enumerate(reversed(digits)):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n

        return total % 10 == 0

    def _calculate_confidence(self, pii_type: str, value: str) -> float:
        """Calculate confidence score for a match."""
        # SSN and credit card have validation, so high confidence
        if pii_type in ("ssn", "credit_card"):
            return 0.95

        # Email is pretty reliable
        if pii_type == "email":
            return 0.9

        # Phone numbers can have false positives
        if pii_type == "phone":
            return 0.7

        # Dates and ZIP codes have many false positives
        if pii_type in ("dob", "zip_code"):
            return 0.5

        return 0.6


# Module-level detector instance
_detector: PIIDetector = None


def get_detector() -> PIIDetector:
    """Get or create the PII detector singleton."""
    global _detector
    if _detector is None:
        _detector = PIIDetector()
    return _detector


def detect_pii(text: str) -> List[PIIMatch]:
    """Convenience function to detect PII."""
    return get_detector().detect(text)


def redact_pii(text: str) -> str:
    """Convenience function to redact PII."""
    redacted, _ = get_detector().redact(text)
    return redacted


def detect_pii_ai(text: str, ai_client) -> List[PIIMatch]:
    """Detect PII using AI-enhanced detection (routed to Haiku for cost efficiency).

    Uses Claude Haiku for pattern recognition to catch edge cases that regex might miss.
    Falls back to regex-only if AI detection fails.

    Args:
        text: Text to scan for PII (limited to 4000 chars for efficiency)
        ai_client: AIClient instance

    Returns:
        List of PIIMatch objects with AI-detected instances
    """
    # Import here to avoid circular dependency
    from src.ai.client import AIClient

    # Limit input for cost efficiency
    text_sample = text[:4000]

    # System prompt for PII detection
    system_prompt = """You are a PII (Personally Identifiable Information) detection specialist.

Your task is to identify PII in text with high precision. Output ONLY valid JSON.

PII types to detect:
- ssn: Social Security Numbers (XXX-XX-XXXX format)
- phone: Phone numbers (various formats)
- email: Email addresses
- dob: Dates of birth (MM/DD/YYYY or similar)
- credit_card: Credit card numbers
- address: Street addresses (house number + street name)
- name: Full names (first + last name combinations)

Output format (JSON only, no other text):
{
  "pii_found": [
    {"type": "ssn", "value": "123-45-6789", "start": 45, "end": 56},
    {"type": "email", "value": "john@example.com", "start": 120, "end": 136}
  ]
}

If no PII found, return: {"pii_found": []}

Be conservative - only flag items you're confident are PII."""

    user_prompt = f"Scan this text for PII:\n\n{text_sample}"

    try:
        # Use fast model - simple pattern recognition task (Phase 29)
        response = ai_client.generate_fast(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        # Parse JSON response
        result = json.loads(response.strip())
        pii_items = result.get("pii_found", [])

        # Convert to PIIMatch objects
        matches = []
        for item in pii_items:
            # Validate that positions are within text bounds
            start = item.get("start", 0)
            end = item.get("end", 0)
            if start < 0 or end > len(text_sample):
                continue

            matches.append(PIIMatch(
                pii_type=item.get("type", "unknown"),
                value=item.get("value", ""),
                start=start,
                end=end,
                confidence=0.85  # AI detection confidence
            ))

        return matches

    except (json.JSONDecodeError, Exception):
        # Fallback to regex detection on AI failure
        return get_detector().detect(text_sample)


def detect_pii_hybrid(text: str, ai_client: Optional[object] = None) -> List[PIIMatch]:
    """Hybrid PII detection combining regex + AI (Phase 29).

    Uses regex for high-confidence patterns, AI for edge cases.
    Routes AI calls to Haiku for 90% cost savings.

    Args:
        text: Text to scan for PII
        ai_client: Optional AIClient instance for AI-enhanced detection

    Returns:
        Combined list of PIIMatch objects (deduplicated)
    """
    # Start with regex detection (fast, free)
    regex_matches = get_detector().detect(text)

    # If no AI client or text is short, use regex only
    if not ai_client or len(text) < 100:
        return regex_matches

    # Add AI detection for edge cases
    ai_matches = detect_pii_ai(text, ai_client)

    # Combine and deduplicate (prefer higher confidence)
    all_matches = regex_matches + ai_matches
    seen_positions = set()
    unique_matches = []

    # Sort by confidence (highest first)
    all_matches.sort(key=lambda m: m.confidence, reverse=True)

    for match in all_matches:
        # Check for overlap with existing matches
        overlaps = False
        for seen_start, seen_end in seen_positions:
            if (match.start >= seen_start and match.start < seen_end) or \
               (match.end > seen_start and match.end <= seen_end):
                overlaps = True
                break

        if not overlaps:
            unique_matches.append(match)
            seen_positions.add((match.start, match.end))

    # Sort by position
    unique_matches.sort(key=lambda m: m.start)

    return unique_matches
