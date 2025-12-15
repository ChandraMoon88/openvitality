from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SafetyDecision:
    allowed: bool
    reasons: List[str]
    actions: List[str]
    metadata: Dict[str, Any]


class GuardrailsCore:
    """
    Master safety aggregator. Lightweight, pluggable, and fast. Each check returns
    a tuple (ok: bool, reason: Optional[str], meta: Optional[dict]). This class
    aggregates the results and decides whether to allow the response.
    """

    def __init__(self,
                 enable_strict_mode: bool = True,
                 extra_detectors: Optional[List] = None):
        self.enable_strict_mode = enable_strict_mode
        self.detectors = extra_detectors or []

    def check(self, text: str, context: Optional[Dict[str, Any]] = None) -> SafetyDecision:
        context = context or {}
        reasons: List[str] = []
        actions: List[str] = []
        meta: Dict[str, Any] = {}

        # Placeholder checks. Plug in real detectors as implemented.
        checks = [
            self._basic_length_check,
            self._deny_empty,
        ] + [getattr(d, "detect", lambda *_: (True, None, {})) for d in self.detectors]

        allowed = True
        for check in checks:
            ok, reason, m = check(text, context)
            if not ok:
                allowed = False
                if reason:
                    reasons.append(reason)
            if m:
                meta.update(m)

        if not allowed and self.enable_strict_mode:
            actions.append("block_response")

        return SafetyDecision(allowed=allowed, reasons=reasons, actions=actions, metadata=meta)

    @staticmethod
    def _basic_length_check(text: str, context: Dict[str, Any]) -> tuple[bool, Optional[str], Dict[str, Any]]:
        if len(text) > 20000:  # arbitrary guard against extremely long inputs
            return False, "input_too_long", {"length": len(text)}
        return True, None, {}

    @staticmethod
    def _deny_empty(text: str, context: Dict[str, Any]) -> tuple[bool, Optional[str], Dict[str, Any]]:
        if not text or not text.strip():
            return False, "empty_input", {}
        return True, None, {}
