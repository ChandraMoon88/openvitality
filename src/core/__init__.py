# src/core/__init__.py
"""
Core module for the AI Hospital application.

This module initializes essential components like configuration, logging,
and exposes the main Orchestrator class to the rest of the application.
"""
import logging
from logging.config import dictConfig

from src import __version__
# from .config_loader import load_config, AppConfig
# from .orchestrator import Orchestrator

# --- Load Configuration ---
# The configuration is loaded once when this module is first imported.
# This makes it available globally as `core.config`.
# config: AppConfig = load_config()

# --- Initialize Logging ---
# Load the logging configuration from the loaded settings.
# dictConfig(config.logging.to_dict())
logger = logging.getLogger(__name__)
# logger.info(f"AI Hospital Core v{__version__} initialized.")
# logger.info(f"Log level set to: {logging.getLevelName(logger.getEffectiveLevel())}")

# --- Expose Key Classes ---
# This makes `Orchestrator` available for import directly from `src.core`.
__all__ = [
    # "Orchestrator",
    # "config",
    "logger",
    "__version__",
]

# A placeholder print statement until the full modules are built
print("src.core package initialized.")
