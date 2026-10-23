import json
import hashlib
import os
import sys

# PYTHONPATH must point to the src directory of the tree being tested
# Run from the tree root with: PYTHONPATH=src python tools/dump_config.py

from niveshdristi.config import CFG

# Get the config file path that was read
import yaml
from pathlib import Path

def find_config_file():
    candidates = [
        Path("config.yaml"),
        Path("config/config.yaml"),
        Path.home() / ".config" / "niveshdristi" / "config.yaml",
        Path("/etc/niveshdristi/config.yaml"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None

# Use the actual CFG (already loaded via get_config)
config_dict = CFG.model_dump()
json_str = json.dumps(config_dict, sort_keys=True, default=str)
md5_hash = hashlib.md5(json_str.encode()).hexdigest()
config_path = find_config_file()

# Print ONE line with everything
print(f"MD5: {md5_hash} | CONFIG_PATH: {config_path} | NIVESHDRISTI_FILE: {__import__('niveshdristi').__file__}")
print(f"JSON: {json_str}")