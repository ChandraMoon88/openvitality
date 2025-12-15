from __future__ import annotations
from typing import Tuple, Optional, Dict, Any

FORBIDDEN_TOPICS = {"politics", "election", "stock market", "programming", "religion"}

class TopicBlacklist:
    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> tuple[bool, Optional[str], Dict[str, Any]]:
        t = (text or "").lower()
        if any(topic in t for topic in FORBIDDEN_TOPICS):
            return False, "topic_forbidden", {}
        return True, None, {}
