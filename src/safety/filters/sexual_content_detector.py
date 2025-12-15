from __future__ import annotations
from typing import Optional, Dict, Any, Tuple

ADULT_TERMS = {"nudes", "sext", "sexual favor"}

class SexualContentDetector:
    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[str], Dict[str, Any]]:
        t = (text or "").lower()
        # Naive distinction; real impl should be context-aware
        if any(term in t for term in ADULT_TERMS):
            return False, "sexual_content_detected", {}
        return True, None, {}
