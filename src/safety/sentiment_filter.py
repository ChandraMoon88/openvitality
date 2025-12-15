from __future__ import annotations
from typing import Tuple, Optional, Dict, Any

class SentimentFilter:
    """Stub sentiment analyzer returning neutral."""
    def analyze(self, text: str) -> float:
        return 0.0

    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[str], Dict[str, Any]]:
        score = self.analyze(text or "")
        if score < -0.8:  # very negative
            return True, "deescalate", {"sentiment": score}
        return True, None, {"sentiment": score}
