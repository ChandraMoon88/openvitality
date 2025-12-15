import sys
import os

try:
    import huggingface_hub
    print(f"Successfully imported huggingface_hub from: {huggingface_hub.__file__}")
except ImportError as e:
    print(f"Failed to import huggingface_hub: {e}")
    print(f"sys.path: {sys.path}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
