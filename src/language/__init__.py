# src/language/__init__.py

import logging
from typing import Dict, Type, Any, Optional

logger = logging.getLogger(__name__)

# --- NLU Engine Factory ---
_NLU_ENGINE_REGISTRY: Dict[str, Type[Any]] = {}
_LOADED_NLU_ENGINES: Dict[str, Any] = {}

def register_nlu_engine(name: str, engine_class: Type[Any]):
    """Registers an NLU engine class with the factory."""
    if name in _NLU_ENGINE_REGISTRY:
        logger.warning(f"NLU engine '{name}' already registered. Overwriting.")
    _NLU_ENGINE_REGISTRY[name] = engine_class
    logger.debug(f"NLU engine '{name}' registered.")

def get_nlu_engine(name: str, **kwargs) -> Any:
    """
    Retrieves and lazily loads an NLU engine instance.
    If the engine is already loaded, returns the existing instance.
    """
    if name not in _NLU_ENGINE_REGISTRY:
        raise ValueError(f"NLU engine '{name}' not registered.")
    
    if name not in _LOADED_NLU_ENGINES:
        logger.info(f"Lazily loading NLU engine: '{name}'.")
        _LOADED_NLU_ENGINES[name] = _NLU_ENGINE_REGISTRY[name](**kwargs)
    
    return _LOADED_NLU_ENGINES[name]

# --- Language Detector Registration ---
_LANGUAGE_DETECTOR: Optional[Any] = None

def register_language_detector(detector_instance: Any):
    """Registers a global language detector instance."""
    global _LANGUAGE_DETECTOR
    if _LANGUAGE_DETECTOR:
        logger.warning("Language detector already registered. Overwriting.")
    _LANGUAGE_DETECTOR = detector_instance
    logger.debug("Language detector registered.")

def get_language_detector() -> Optional[Any]:
    """Returns the registered global language detector instance."""
    return _LANGUAGE_DETECTOR

# --- Default Language Fallback ---
DEFAULT_LANGUAGE: str = "en"

def set_default_language(lang_code: str):
    """Sets the default fallback language."""
    global DEFAULT_LANGUAGE
    DEFAULT_LANGUAGE = lang_code
    logger.info(f"Default language set to '{DEFAULT_LANGUAGE}'.")

def get_default_language() -> str:
    """Returns the current default language."""
    return DEFAULT_LANGUAGE

# Example of how NLU engines might register themselves (e.g., from nlu_engine.py)
# from .nlu_engine import NLUEngine
# register_nlu_engine("default", NLUEngine)

logger.info("src.language package initialized.")
