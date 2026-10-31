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
# Calculate MD5 without __file__ for equality check
config_for_md5 = {k: v for k, v in config_dict.items() if k != "__file__"}
json_str_for_md5 = json.dumps(config_for_md5, sort_keys=True, default=str)
md5_hash = hashlib.md5(json_str_for_md5.encode()).hexdigest()

# Include __file__ in the JSON output for path verification
config_dict["__file__"] = __import__('niveshdristi').__file__
json_str = json.dumps(config_dict, sort_keys=True, default=str)
config_path = find_config_file()

# Print ONE line with everything
print(f"MD5: {md5_hash} | CONFIG_PATH: {config_path} | NIVESHDRISTI_FILE: {__import__('niveshdristi').__file__}")
print(f"JSON: {json_str}")