# src/__init__.py
"""
Main source package for the Free AI Hospital application.
"""

# Try to read the version from a file, otherwise default to a development version.
# This makes the version accessible as `src.VERSION`.
try:
    with open('VERSION', 'r') as f:
        __version__ = f.read().strip()
except FileNotFoundError:
    __version__ = "0.1.0-dev"

# This file's existence makes 'src' a Python package.
# It can be left empty or used to expose key components from submodules.
