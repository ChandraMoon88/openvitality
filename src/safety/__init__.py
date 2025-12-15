"""
Safety package initialization.

This package contains safety filters, compliance validators, privacy utilities,
and guardrail components used to ensure safe and compliant behavior across the
healthcare voice AI system. The modules within should be designed to be:
- Fast (low latency)
- Deterministic and auditable
- Configurable via config files and env vars
- Non-invasive: never crash upstream flows; return explicit allow/deny decisions

Structure (planned):
- guardrails_core.py: Orchestrates safety checks and aggregates results
- hallucination_detector.py: Verifies claims against retrieved sources
- jailbreak_defense.py: Detects prompt injection/jailbreak attempts
- profanity_filter.py: Context-aware profanity detection
- topic_blacklist.py: Keeps the assistant on medical topics
- sentiment_filter.py: Detects and de-escalates high anger/negative sentiment
- human_handoff_trigger.py: Decides when to escalate to a human
- filters/: Fine-grained detectors (violence, self-harm, hate, sexual content)
- privacy/: PII/PHI handling, retention, consent, right-to-be-forgotten
- compliance/: HIPAA, GDPR, DPDP validators

All modules should avoid importing heavy ML libraries at import-time; prefer lazy
initialization to keep application cold start fast.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Version for auditing
__version__ = "0.1.0"

# Export convenience imports (when available). These are optional to avoid
# import-time failures if submodules are not yet implemented.
try:
    from .guardrails_core import GuardrailsCore  # type: ignore
except Exception:  # pragma: no cover - optional at import time
    GuardrailsCore = None  # type: ignore

__all__ = [
    "GuardrailsCore",
    "__version__",
]
