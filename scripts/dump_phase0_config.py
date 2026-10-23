import sys
# Remove current repo from path
sys.path = [p for p in sys.path if 'NiveshDristii' not in p]
# Add phase0 src
sys.path.insert(0, r'D:\Nivesh Dristi\phase0_wt\src')
from niveshdristi.config import CFG
import json, hashlib
from pathlib import Path

def find_config_file():
    candidates = [Path('config.yaml'), Path('config/config.yaml'), Path.home() / '.config' / 'niveshdristi' / 'config.yaml', Path('/etc/niveshdristi/config.yaml')]
    for c in candidates:
        if c.exists():
            return str(c)
    return None

config_dict = CFG.model_dump()
json_str = json.dumps(config_dict, sort_keys=True, default=str)
md5_hash = hashlib.md5(json_str.encode()).hexdigest()
config_path = find_config_file()
print(f'MD5: {md5_hash} | CONFIG_PATH: {config_path} | NIVESHDRISTI_FILE: {__import__("niveshdristi").__file__}')
print(f'JSON: {json_str}')