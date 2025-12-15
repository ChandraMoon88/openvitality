from __future__ import annotations
from typing import Dict
import re

PHONE = re.compile(r"\b\+?\d[\d\-\s]{6,}\b")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

class PIIScrubber:
    """Very lightweight PII scrubber (placeholder). Replace with Presidio in prod."""
    def scrub(self, text: str) -> str:
        t = text or ""
        t = PHONE.sub("<PHONE>", t)
        t = EMAIL.sub("<EMAIL>", t)
        return t
