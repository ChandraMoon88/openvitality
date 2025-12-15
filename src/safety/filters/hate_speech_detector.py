from __future__ import annotations
from typing import Optional, Dict, Any, Tuple

SLURS = {"slur1", "slur2"}  # placeholder; replace with proper model or curated lists

class HateSpeechDetector:
    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[str], Dict[str, Any]]:
        t = (text or "").lower()
        if any(s in t for s in SLURS):
            return False, "hate_speech_detected", {}
        return True, None, {}
