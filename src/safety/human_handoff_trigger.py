from __future__ import annotations
from typing import Dict, Any, Optional, Tuple

class HumanHandoffTrigger:
    """Decides when to escalate to a human.
    Stub: Never triggers by default; expose a simple API for future wiring.
    """
    def __init__(self, min_low_conf_turns: int = 2):
        self.min_low_conf_turns = min_low_conf_turns

    def should_handoff(self, history: list[Dict[str, Any]], last_confidence: float) -> bool:
        if last_confidence < 0.4:
            low = [h for h in history[-self.min_low_conf_turns:] if h.get("confidence", 1.0) < 0.4]
            return len(low) >= self.min_low_conf_turns
        return False
