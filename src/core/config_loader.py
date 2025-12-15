# src/core/config_loader.py
"""
Dynamically loads, merges, and validates configuration for the application.
"""
import os
from pathlib import Path
from functools import lru_cache
import yaml
from typing import Dict, Any
from dotenv import load_dotenv

# This would be a Pydantic model for schema validation
# from .schemas import AppConfigSchema 

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent.parent / ".env")

@lru_cache(maxsize=1)
def load_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Loads a single YAML file and returns its content.
    Uses LRU cache to avoid reading the same file multiple times.
    """
    if not file_path.is_file():
        # In a real app, log this error
        print(f"Warning: Config file not found at {file_path}")
        return {}
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def get_config(region: str = "default") -> Dict[str, Any]:
    """
    Loads and merges configuration files based on a specified region.
    
    The loading order is:
    1. `settings.yaml` (base settings)
    2. `feature_flags.yaml`
    3. `logging_config.yaml`
    4. `regions/default.yaml` (fallback region settings)
    5. `regions/<region>.yaml` (specific region settings, overrides default)
    6. Environment variables (overrides everything)
    """
    # 1. Load base configurations
    base_config = load_yaml(CONFIG_DIR / "settings.yaml")
    base_config.update(load_yaml(CONFIG_DIR / "feature_flags.yaml"))
    base_config["logging"] = load_yaml(CONFIG_DIR / "logging_config.yaml")

    # 2. Load regional configurations
    default_region_config = load_yaml(CONFIG_DIR / "regions/default.yaml")
    specific_region_config = load_yaml(CONFIG_DIR / f"regions/{region}.yaml")

    # Merge regional configs (specific overrides default)
    merged_region_config = {**default_region_config, **specific_region_config}
    base_config["region"] = merged_region_config
    
    # 3. Override with environment variables
    # Example: env var `APP_DEBUG_MODE=false` overrides `debug_mode: true` in YAML
    for key, value in os.environ.items():
        if key.startswith("APP_"):
            # Simple conversion for nested keys, e.g., REGION_CURRENCY -> ['region', 'currency']
            config_keys = key.replace("APP_", "").lower().split('_')
            
            temp_config = base_config
            for k in config_keys[:-1]:
                temp_config = temp_config.setdefault(k, {})
            
            # Attempt to convert value type
            if value.lower() in ['true', 'false']:
                temp_config[config_keys[-1]] = value.lower() == 'true'
            elif value.isdigit():
                temp_config[config_keys[-1]] = int(value)
            else:
                temp_config[config_keys[-1]] = value

    # 4. Schema Validation (conceptual)
    # try:
    #     validated_config = AppConfigSchema(**base_config)
    # except ValidationError as e:
    #     raise SystemExit(f"FATAL: Configuration validation failed: {e}")
    # return validated_config

    return base_config

def validate_required_env_vars():
    """
    Checks for the presence of essential environment variables.
    """
    required_vars = ["GEMINI_API_KEY", "DATABASE_URL"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise SystemExit(f"FATAL: Missing required environment variables: {', '.join(missing_vars)}")

# Conceptual hot-reload function
# This would typically be run in a separate thread/process managed by config_loader_dynamic.py
def _hot_reload_callback():
    """

    Clears the cache, forcing configs to be reloaded from disk on next access.
    """
    print("Change detected in config files. Clearing config cache for hot reload.")
    load_yaml.cache_clear()
    get_config.cache_clear() # If get_config was also cached

# On first import, check for required secrets
validate_required_env_vars()

# Example usage:
# if __name__ == "__main__":
#     config = get_config(region="india")
#     import json
#     print(json.dumps(config, indent=2))

#     # Simulate env var override
#     os.environ["APP_DEBUG_MODE"] = "false"
#     os.environ["APP_REGION_CURRENCY"] = "Rupee"
#     config_reloaded = get_config(region="india")
#     print("\nAfter env var override:")
#     print(json.dumps(config_reloaded, indent=2))
