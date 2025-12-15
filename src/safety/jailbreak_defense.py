from __future__ import annotations
from typing import Tuple, Optional, Dict, Any
import re

JAILBREAK_PATTERNS = [
    re.compile(r"ignore (all|previous) instructions", re.I),
    re.compile(r"do anything now", re.I),
    re.compile(r"role\s*play\s+as", re.I),
]

class JailbreakDefense:
    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[str], Dict[str, Any]]:
        for pat in JAILBREAK_PATTERNS:
            if pat.search(text or ""):
                return False, "jailbreak_detected", {"pattern": pat.pattern}
        return True, None, {}
