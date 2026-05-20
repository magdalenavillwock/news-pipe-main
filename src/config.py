# src/config.py
from pathlib import Path
from typing import Optional

import yaml


def load_config(path: Optional[str] = None) -> dict:
    if path is None:
        config_path = Path.cwd() / "config.yaml"
    else:
        config_path = Path(path)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        return yaml.safe_load(f)
