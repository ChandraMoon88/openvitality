from __future__ import annotations
from typing import Optional, Dict, Any, Tuple

KEYWORDS = {"kill myself", "end it all", "not worth living", "goodbye forever"}

class SelfHarmDetector:
    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[str], Dict[str, Any]]:
        t = (text or "").lower()
        if any(k in t for k in KEYWORDS):
            return False, "self_harm_detected", {}
        return True, None, {}
