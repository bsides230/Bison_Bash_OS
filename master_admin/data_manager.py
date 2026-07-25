import json
import os
import time
from datetime import datetime
from pathlib import Path
from filelock import FileLock

DATA_DIR = Path("master_admin/data")
ARCHIVE_DIR = DATA_DIR / "archive"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

PLAYERS_FILE = DATA_DIR / "players.json"
SETTINGS_FILE = Path("game_hub/admin/admin_settings.json")
ACTIVE_LINEUP_FILE = Path("game_hub/data/active_lineup.json")

# Initialize default files if they don't exist
if not PLAYERS_FILE.exists():
    with open(PLAYERS_FILE, "w") as f:
        json.dump({"players": {}}, f)

if not SETTINGS_FILE.exists():
    with open(SETTINGS_FILE, "w") as f:
        json.dump({
            "tailscale_enforcement": False,
            "tailscale_ip_pool": "100.",
            "bind_host": "127.0.0.1",
            "bind_port": 8000,
            "bison_dash": {
                "state": "Betting_Open",
                "timers": {
                    "Soft_Closure": 10,
                    "Closed_Intros": 60,
                    "Race_Sprint": 30,
                    "Results_Payout": 120
                },
                "state_start_time": time.time()
            }
        }, f)

if not ACTIVE_LINEUP_FILE.exists():
    with open(ACTIVE_LINEUP_FILE, "w") as f:
        json.dump({"lineup": []}, f)

def read_data(filepath: Path) -> dict:
    with open(filepath, "r") as f:
        return json.load(f)

def write_data(filepath: Path, data: dict, backup: bool = True):
    # Acquire a file lock to prevent race conditions during write/backup
    lock_path = str(filepath) + ".lock"
    with FileLock(lock_path):
        # 1. Write the current state to the primary file
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        if not backup:
            return

        # 2. Trigger incremental state redundancy copy
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filepath.stem
        ext = filepath.suffix
        backup_filename = f"{filename}_backup_{timestamp}{ext}"
        backup_path = ARCHIVE_DIR / backup_filename

        with open(backup_path, "w") as f:
            json.dump(data, f, indent=2)
