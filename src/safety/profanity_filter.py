from __future__ import annotations
from typing import Tuple, Optional, Dict, Any

# Minimal placeholder list; replace with context-aware library
BLOCKLIST = {"idiot", "stupid", "dumb"}

class ProfanityFilter:
    def is_profane(self, text: str) -> bool:
        t = (text or "").lower()
        return any(bad in t for bad in BLOCKLIST)

    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[str], Dict[str, Any]]:
        if self.is_profane(text):
            return False, "profanity_detected", {}
        return True, None, {}
