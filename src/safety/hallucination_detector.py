from __future__ import annotations
from typing import Dict, Any, List, Tuple

import logging
logger = logging.getLogger(__name__)

class HallucinationDetector:
    """
    Lightweight stub that compares statements against retrieved sources.
    Real implementation should use NLI (entailment) and RAG evidence checks.
    """
    def __init__(self, confidence_threshold: float = 0.6):
        self.confidence_threshold = confidence_threshold

    def validate_against_sources(self, answer: str, sources: List[Dict[str, Any]]) -> Tuple[bool, float, List[str]]:
        """
        Returns (supported, confidence, reasons)
        Stub behavior: If there are any sources, assume supported at medium confidence.
        """
        if not sources:
            return False, 0.0, ["no_sources"]
        return True, 0.7, []
