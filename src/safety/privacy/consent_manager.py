from __future__ import annotations
from typing import Dict, Any, Optional
import time

class ConsentManager:
    """In-memory stub; replace with persistent store in production."""
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def set_consent(self, user_id: str, consent_type: str, value: bool) -> None:
        self._store.setdefault(user_id, {})[consent_type] = {"value": value, "ts": int(time.time())}

    def get_consent(self, user_id: str, consent_type: str) -> Optional[Dict[str, Any]]:
        return self._store.get(user_id, {}).get(consent_type)
