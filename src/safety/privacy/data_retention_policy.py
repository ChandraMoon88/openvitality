from __future__ import annotations
from typing import Dict, Any

DEFAULT_RULES = {
    "audio_recordings_days": 7,
    "chat_transcripts_years": 10,
    "system_logs_days": 90,
    "backups_years": 1,
}

class DataRetentionPolicy:
    def __init__(self, rules: Dict[str, Any] | None = None):
        self.rules = rules or DEFAULT_RULES

    def get_rules(self) -> Dict[str, Any]:
        return dict(self.rules)
