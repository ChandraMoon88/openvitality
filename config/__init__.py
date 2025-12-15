# config/__init__.py
"""
Configuration System for the Free AI Hospital.

This package handles loading all configuration from YAML files and environment
variables, providing a centralized and easy-to-use interface for accessing
settings throughout the application.

The configuration is loaded lazily on first access to save startup time.
This means the files are only read from disk when a setting is requested,
not when the application server starts.

Main Components:
- settings.yaml: Core application settings.
- feature_flags.yaml: Toggles for application features.
- logging_config.yaml: Configuration for logging formatters and handlers.
- regions/*.yaml: Country-specific settings.
- prompts/*.yaml: System prompts and personas for the AI.
"""

# The version of the application, read from the root of the project.
# This helps in tracking deployed versions.
try:
    with open('VERSION', 'r') as f:
        VERSION = f.read().strip()
except FileNotFoundError:
    VERSION = "0.1.0-dev"


# The main config loading function would be defined in another file
# within this package, and imported here for easy access.
# For example:
# from .loader import load_config
#
# # Expose the main config object to the rest of the application
# config = load_config()

# To demonstrate the structure, we'll keep it simple for now.
print("Configuration package initialized.")

__all__ = ['VERSION']
