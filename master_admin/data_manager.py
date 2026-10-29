import copy
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
PLAYERS_DIR = DATA_DIR / "players"
PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
ECONOMY_FILE = DATA_DIR / "economy_config.json"
SETTINGS_FILE = Path("game_hub/admin/admin_settings.json")
ACTIVE_LINEUP_FILE = Path("game_hub/data/active_lineup.json")
SLIDES_DIR = Path("master_admin/static/slides")
SLIDES_DIR.mkdir(parents=True, exist_ok=True)
SLIDES_MANIFEST_FILE = DATA_DIR / "slides_manifest.json"
SLIDESHOW_STATE_FILE = DATA_DIR / "slideshow_state.json"
FINALIZED_LINKS_FILE = DATA_DIR / "finalized_links.json"

DEFAULT_FINALIZED_LINKS = [
    {
        "id": "portal",
        "title": "Mobile Player Portal",
        "port": 8009,
        "path": "/portal",
        "subtitle": "Scan with phone camera to view wallet balance & pass",
        "icon": "📱",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "signup",
        "title": "Attendee Sign-Up",
        "port": 8009,
        "path": "/signup",
        "subtitle": "Register now to receive starter tokens & your 4-digit PIN",
        "icon": "📝",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "pass",
        "title": "Player Pass Lookup",
        "port": 8009,
        "path": "/pass",
        "subtitle": "Enter your 4-digit PIN to show your digital badge",
        "icon": "💳",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "kiosk1",
        "title": "Bison Dash Betting Tablet 1",
        "port": 8008,
        "path": "/kiosk?tablet=1",
        "subtitle": "Self-service touchscreen terminal for live race wagers",
        "icon": "🕹️",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "kiosk2",
        "title": "Bison Dash Betting Tablet 2",
        "port": 8008,
        "path": "/kiosk?tablet=2",
        "subtitle": "Self-service touchscreen terminal for live race wagers",
        "icon": "🕹️",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "gauntlet",
        "title": "AI Gauntlet Challenge",
        "port": 8007,
        "path": "/",
        "subtitle": "Test your nerve in the neural gateway challenge",
        "icon": "⚡",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "mint",
        "title": "Token Mint & Cash Desk",
        "port": 8005,
        "path": "/",
        "subtitle": "Volunteer station to add donation tokens to player wallets",
        "icon": "🪙",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "n64",
        "title": "N64 Arena Match Deck",
        "port": 8004,
        "path": "/",
        "subtitle": "Mario Kart & GoldenEye 1v1 tournament station",
        "icon": "🎮",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "bughunt",
        "title": "Bug Bounty: Kids Booth",
        "port": 8003,
        "path": "/",
        "subtitle": "Physical 60-second bug collection challenge for kids",
        "icon": "🐛",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "bison_arena",
        "title": "Bison Dash Stadium Arena",
        "port": 8001,
        "path": "/",
        "subtitle": "Main race track display and betting odds board",
        "icon": "🏁",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "bison_projector",
        "title": "Bison Dash Stadium Projector",
        "port": 8001,
        "path": "/projector",
        "subtitle": "Jumbotron stadium broadcast screen",
        "icon": "📽️",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "slideshow",
        "title": "Stadium Slideshow",
        "port": 8010,
        "path": "/slideshow",
        "subtitle": "Full-screen projector slideshow and live race cut-in display",
        "icon": "📽️",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "presenter",
        "title": "Presenter Slide Remote",
        "port": 8010,
        "path": "/presenter",
        "subtitle": "Mobile remote control to advance presentation slides",
        "icon": "📱",
        "is_custom": False,
        "url": ""
    },
    {
        "id": "manifest",
        "title": "Full Player Manifest",
        "port": 8000,
        "path": "/manifest",
        "subtitle": "Master roster of all registered attendees & PINs",
        "icon": "👥",
        "is_custom": False,
        "url": ""
    }
]

DEFAULT_SLIDES_MANIFEST = {
    "default_duration": 10,
    "slides": [
        {
            "id": "builtin_welcome",
            "type": "builtin_welcome",
            "title": "Welcome to the Arena",
            "enabled": True,
            "duration": 10,
            "order": 0
        },
        {
            "id": "builtin_qr",
            "type": "builtin_qr",
            "title": "Mobile PIN Pass & QR",
            "enabled": True,
            "duration": 10,
            "order": 1
        },
        {
            "id": "builtin_leaderboard",
            "type": "leaderboard",
            "title": "Live Stadium Leaderboard",
            "enabled": True,
            "duration": 12,
            "order": 2
        },
        {
            "id": "builtin_booths",
            "type": "builtin_booths",
            "title": "Interactive Arcade Stations",
            "enabled": True,
            "duration": 10,
            "order": 3
        }
    ],
    "presentation_slides": [],
    "branding": {
        "logo_url": "/static/img/bison_logo.png",
        "show_header_title": True,
        "show_clock": True
    }
}

DEFAULT_SLIDESHOW_STATE = {
    "mode": "slideshow",
    "countdown": {
        "active": False,
        "duration_seconds": 300,
        "target_timestamp": 0,
        "title": "Next Bison Dash Race",
        "started_at": 0
    },
    "presentation": {
        "active": False,
        "current_index": 0,
        "title": "Stage Presentation"
    },
    "restart_trigger": 0
}

DEFAULT_ECONOMY_CONFIG = {
    "initial_allotment": 50,
    "tokens_per_dollar": 5,
    "costs": {
        "n64": 0,
        "bughunt": 1,
        "gauntlet": 4,
        "bison_dash_min_bet": 1
    },
    "payouts": {
        "n64_winner": 10,
        "bughunt_bugs_per_token": 5,
        "bughunt_pity_tokens": 1,
        "plinko_slots": [1, 1, 2, 2, 5, 2, 2, 1, 1],
        "gauntlet": {
            "stage1": 2,
            "stage2": 3,
            "stage3": 5,
            "stage4": 8,
            "vault_jackpot": 25,
            "vault_runner_up": 10
        },
        "bison_dash_multiplier": 2.0
    },
    "timers": {
        "bughunt_duration": 60
    }
}

# Initialize default files if they don't exist
if not PLAYERS_FILE.exists():
    with open(PLAYERS_FILE, "w") as f:
        json.dump({"players": {}}, f)

if not ECONOMY_FILE.exists():
    with open(ECONOMY_FILE, "w") as f:
        json.dump(DEFAULT_ECONOMY_CONFIG, f, indent=2)

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

if not SLIDES_MANIFEST_FILE.exists():
    with open(SLIDES_MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_SLIDES_MANIFEST, f, indent=2)

if not SLIDESHOW_STATE_FILE.exists():
    with open(SLIDESHOW_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_SLIDESHOW_STATE, f, indent=2)

def read_data(filepath: Path, retries: int = 5) -> dict:
    lock_path = str(filepath) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        for attempt in range(retries):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                if attempt == retries - 1:
                    raise
                time.sleep(0.01)

def write_data(filepath: Path, data: dict, backup: bool = True):
    # Acquire a file lock to prevent race conditions during write/backup
    lock_path = str(filepath) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        # 1. Atomically write via temporary file replacement
        tmp_file = filepath.with_name(f"{filepath.name}.tmp_{time.time_ns()}")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp_file.replace(filepath)

        if not backup:
            return

        # 2. Trigger incremental state redundancy copy
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filepath.stem
        ext = filepath.suffix
        backup_filename = f"{filename}_backup_{timestamp}{ext}"
        backup_path = ARCHIVE_DIR / backup_filename

        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # 3. Rolling Backup Eviction: strictly preserve recent backups (minimum 10)
        # Protect player archives from eviction so attendee data is never lost
        existing_backups = sorted(
            ARCHIVE_DIR.glob(f"{filename}_backup_*{ext}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        for old_backup in existing_backups[10:]:
            try:
                if filename == "players" and old_backup.stat().st_size > 100:
                    continue
                old_backup.unlink()
            except OSError:
                pass

def generate_unique_pin(existing_pins: set) -> str:
    """Generates a random unique 4-digit PIN between 1000 and 9999."""
    import random
    trivial = {"1111", "2222", "3333", "4444", "5555", "6666", "7777", "8888", "9999", "1234", "0000", "4321"}
    for _ in range(10000):
        pin = str(random.randint(1000, 9999))
        if pin not in existing_pins and pin not in trivial:
            return pin
    for p in range(1000, 10000):
        pin = str(p)
        if pin not in existing_pins:
            return pin
    return "9999"

# --- Individual Player JSON & Concurrency Management ---

def _ensure_player_storage_sync():
    """Initial startup sync: writes individual JSON files for any existing players in players.json."""
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    if PLAYERS_FILE.exists():
        try:
            data = read_data(PLAYERS_FILE)
            for pid, pdata in data.get("players", {}).items():
                pfile = PLAYERS_DIR / f"{pid}.json"
                if not pfile.exists():
                    rec = dict(pdata)
                    rec["id"] = pid
                    write_data(pfile, rec, backup=False)
        except Exception as e:
            print(f"[DataManager] Storage sync warning: {e}")

_ensure_player_storage_sync()

def get_player_file(player_id: str) -> Path:
    """Returns the individual JSON file path for a player."""
    clean = str(player_id).strip()
    return PLAYERS_DIR / f"{clean}.json"

def save_player_file(player_dict: dict) -> dict:
    """
    Saves an individual player's JSON file atomically with a per-player file lock,
    then synchronizes the player to the main players.json registry.
    """
    pid = player_dict.get("id")
    if not pid:
        return player_dict
    
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    pfile = get_player_file(pid)
    
    rec = dict(player_dict)
    rec["id"] = pid
    if "updated_at" not in rec:
        rec["updated_at"] = time.time()
        
    write_data(pfile, rec, backup=False)
    sync_player_to_registry(rec)
    return rec

def sync_player_to_registry(player_dict: dict) -> None:
    """Safely updates a single player record in the main players.json registry."""
    pid = player_dict.get("id")
    if not pid:
        return
    lock_path = str(PLAYERS_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        data = read_data(PLAYERS_FILE)
        if "players" not in data or not isinstance(data["players"], dict):
            data["players"] = {}
        rec = dict(player_dict)
        rec["id"] = pid
        existing = data["players"].get(pid)
        if existing and isinstance(existing, dict):
            if float(existing.get("updated_at", 0)) > float(rec.get("updated_at", 0)):
                return
        data["players"][pid] = rec
        write_data(PLAYERS_FILE, data)

def rebuild_registry_from_player_files() -> dict:
    """Recompiles the main players.json registry from all individual player JSON files."""
    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    compiled = {}
    for p_file in PLAYERS_DIR.glob("*.json"):
        try:
            p_data = read_data(p_file)
            if isinstance(p_data, dict) and "id" in p_data:
                pid = p_data["id"]
                compiled[pid] = dict(p_data)
        except Exception as e:
            print(f"[DataManager] Warning reading {p_file}: {e}")
            
    lock_path = str(PLAYERS_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        write_data(PLAYERS_FILE, {"players": compiled})
    return compiled

def get_all_players() -> list:
    """Returns a list of all player dictionaries from the manifest, reconciled with individual files."""
    data = read_data(PLAYERS_FILE)
    players_dict = data.get("players", {})
    dirty = False

    # Check individual player files to guarantee zero data loss
    if PLAYERS_DIR.exists():
        for pfile in PLAYERS_DIR.glob("*.json"):
            pid = pfile.stem
            if pid not in players_dict:
                try:
                    pdata = read_data(pfile)
                    if isinstance(pdata, dict) and ("id" in pdata or "email" in pdata or "pin" in pdata):
                        if "id" not in pdata:
                            pdata["id"] = pid
                        players_dict[pid] = pdata
                        dirty = True
                except Exception:
                    pass

    if dirty:
        data["players"] = players_dict
        try:
            write_data(PLAYERS_FILE, data, backup=False)
        except Exception:
            pass

    player_list = []
    for pid, pdata in players_dict.items():
        item = dict(pdata)
        item["id"] = pid
        if "name" not in item:
            item["name"] = pid
        if "email" not in item:
            item["email"] = ""
        if "pin" not in item:
            item["pin"] = "----"
        if "balance" not in item:
            item["balance"] = 0
        if "total_wagers" not in item:
            item["total_wagers"] = 0
        if "total_winnings" not in item:
            item["total_winnings"] = 0
        player_list.append(item)
    return player_list

def get_player(identifier: str) -> dict | None:
    """Retrieves a single player dictionary by ID, 4-digit PIN, Email, or Display Name."""
    if not identifier:
        return None
    raw = str(identifier).strip()
    norm = raw.lower()

    # 1. Exact ID match directly from individual player JSON file
    pfile = get_player_file(raw)
    if pfile.exists():
        try:
            p = read_data(pfile)
            if isinstance(p, dict) and p.get("id") == raw:
                return p
        except Exception:
            pass

    data = read_data(PLAYERS_FILE)
    players = data.get("players", {})

    # 2. Exact ID match in registry
    if raw in players:
        p = dict(players[raw])
        p["id"] = raw
        return p

    # 3. PIN match
    for pid, pdata in players.items():
        if str(pdata.get("pin", "")).strip() == raw:
            p = dict(pdata)
            p["id"] = pid
            return p

    # 4. Email match
    for pid, pdata in players.items():
        if pdata.get("email", "").strip().lower() == norm:
            p = dict(pdata)
            p["id"] = pid
            return p

    # 5. Display Name match
    for pid, pdata in players.items():
        if pdata.get("name", "").strip().lower() == norm:
            p = dict(pdata)
            p["id"] = pid
            return p

    return None

def get_player_by_email(email: str) -> dict | None:
    """Finds a player by email (case-insensitive)."""
    norm_email = email.strip().lower()
    data = read_data(PLAYERS_FILE)
    for pid, pdata in data.get("players", {}).items():
        if pdata.get("email", "").strip().lower() == norm_email:
            p = dict(pdata)
            p["id"] = pid
            return p
    return None

def get_player_by_pin(pin: str) -> dict | None:
    """Finds a player by their 4-digit PIN."""
    target_pin = str(pin).strip()
    data = read_data(PLAYERS_FILE)
    for pid, pdata in data.get("players", {}).items():
        if str(pdata.get("pin", "")).strip() == target_pin:
            p = dict(pdata)
            p["id"] = pid
            return p
    return None

# =========================================================================
# PIN AUTHENTICATION, LOOKUP & 10-SECOND CONCURRENCY RATE LIMITING
# =========================================================================

# In-memory dictionary tracking the last activity timestamp for each PIN
pin_last_used: dict[str, float] = {}
RATE_LIMIT_FILE = DATA_DIR / "pin_rate_limit.json"

def _load_pin_rate_limits() -> dict[str, float]:
    """Loads rate limit timestamps from shared file and merges into memory."""
    global pin_last_used
    if RATE_LIMIT_FILE.exists():
        try:
            with open(RATE_LIMIT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if k not in pin_last_used or v > pin_last_used[k]:
                            pin_last_used[k] = float(v)
        except Exception:
            pass
    return pin_last_used

def _save_pin_rate_limits(pin: str, timestamp: float):
    """Saves rate limit timestamp to memory and shared file."""
    global pin_last_used
    pin_last_used[pin] = timestamp
    try:
        data = {}
        if RATE_LIMIT_FILE.exists():
            try:
                with open(RATE_LIMIT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[pin] = timestamp
        cutoff = timestamp - 60.0
        cleaned = {k: v for k, v in data.items() if v > cutoff}
        with open(RATE_LIMIT_FILE, "w", encoding="utf-8") as f:
            json.dump(cleaned, f)
    except Exception:
        pass

def check_and_update_pin_cooldown(pin: str, cooldown_seconds: float = 10.0) -> tuple[bool, str | None]:
    """
    Checks if a PIN is within the 10-second concurrency & anti-spam cooldown lock.
    Returns (True, None) if allowed (and updates timestamp).
    Returns (False, "Please wait before using your code again.") if rejected.
    """
    clean_pin = str(pin).strip()
    if not clean_pin:
        return True, None

    now = time.time()
    _load_pin_rate_limits()
    last = pin_last_used.get(clean_pin, 0.0)
    elapsed = now - last

    if elapsed < cooldown_seconds:
        return False, "Please wait before using your code again."

    _save_pin_rate_limits(clean_pin, now)
    return True, None

def lookup_attendee_by_pin(pin: str) -> dict | None:
    """
    Looks up attendee record by 4-digit numeric PIN.
    Returns attendee dict with display_name, email, balance, id, pin, or None if invalid.
    """
    clean_pin = str(pin).strip()
    if not clean_pin or len(clean_pin) != 4 or not clean_pin.isdigit():
        return None
    player = get_player_by_pin(clean_pin)
    if not player:
        return None
    return {
        "id": player["id"],
        "display_name": player.get("name") or player.get("display_name") or "Attendee",
        "email": player.get("email", ""),
        "balance": int(player.get("balance", 0)),
        "pin": clean_pin
    }

def get_pin_for_player(identifier: str) -> str | None:
    """Finds player PIN given an id, email, or pin."""
    p = get_player(identifier)
    if not p:
        p = get_player_by_email(identifier)
    if not p:
        p = get_player_by_pin(identifier)
    if p and "pin" in p:
        return str(p["pin"]).strip()
    return None

TOKEN_LEDGER_FILE = DATA_DIR / "token_ledger.jsonl"
ROOT_TOKEN_LEDGER_FILE = Path("data/token_ledger.jsonl")

def mint_tokens(pin: str, donation_amount: float, tokens_to_add: int) -> dict | None:
    """
    Atomically credit attendee balance by PIN.
    Appends transaction to ledger (data/token_ledger.jsonl) with:
    timestamp, pin, donation_amount, tokens_credited, and new_balance.
    Updates pin_last_used[pin] = current_time.
    Returns dict with {"success": True, "new_balance": new_balance} or None if PIN invalid.
    """
    clean_pin = str(pin).strip()
    if not clean_pin or len(clean_pin) != 4 or not clean_pin.isdigit():
        return None

    player = get_player_by_pin(clean_pin)
    if not player:
        return None

    pid = player["id"]
    tokens = int(tokens_to_add)

    # 1. Atomically credit balance
    updated = adjust_player_balance(pid, tokens)
    new_balance = updated["balance"] if updated else (player.get("balance", 0) + tokens)

    # 2. Append transaction to token_ledger.jsonl
    now_ts = time.time()
    now_iso = datetime.now().isoformat()
    record = {
        "timestamp": now_ts,
        "timestamp_iso": now_iso,
        "pin": clean_pin,
        "player_id": pid,
        "display_name": player.get("name") or player.get("display_name") or "Attendee",
        "email": player.get("email", ""),
        "donation_amount": float(donation_amount),
        "tokens_credited": tokens,
        "new_balance": new_balance
    }

    TOKEN_LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ROOT_TOKEN_LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)

    line_str = json.dumps(record) + "\n"
    ledger_lock = str(TOKEN_LEDGER_FILE) + ".lock"
    with FileLock(ledger_lock, is_singleton=True):
        with open(TOKEN_LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(line_str)
        try:
            with open(ROOT_TOKEN_LEDGER_FILE, "a", encoding="utf-8") as f:
                f.write(line_str)
        except Exception:
            pass

    # 3. Update pin_last_used[pin] = current_time
    _save_pin_rate_limits(clean_pin, now_ts)

    return {
        "success": True,
        "new_balance": new_balance
    }

def get_token_ledger() -> list[dict]:
    """Returns all transaction records from the token ledger."""
    entries = []
    target = TOKEN_LEDGER_FILE if TOKEN_LEDGER_FILE.exists() else ROOT_TOKEN_LEDGER_FILE
    if target.exists():
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except Exception:
                        pass
    return entries

def is_test_account(p: dict) -> bool:
    """Identifies synthetic/test accounts generated by automated test suites."""
    if not isinstance(p, dict):
        return False
    pid = str(p.get("id", "")).lower()
    email = str(p.get("email", "")).lower()
    name = str(p.get("name", "")).lower()

    # Never delete explicitly protected or real accounts
    if p.get("_protected") or p.get("is_real"):
        return False

    # Test ID prefixes from automated benchmark runners
    if any(pid.startswith(prefix) for prefix in ("autotest_", "bench_", "tmp_")):
        return True

    # Only automated test suite emails (explicit automated patterns)
    if email.startswith("test_") or email.startswith("user") and email.endswith("@test.com"):
        return True
    if email.startswith("attendee_") and email.endswith("@venue.com"):
        return True
    if email.startswith("tester_gauntlet@") or email.startswith("broke_attendee@") or email.startswith("signee_test_user@"):
        return True

    # Automated benchmark names
    if name.startswith("attendee_0") or name.startswith("player_") or name in ("gauntletchamp", "brokeattendee"):
        return True

    return False

def clear_all_players(force: bool = False, keep_real_players: bool = True) -> bool:
    """
    Clears player accounts.
    By default (force=False, keep_real_players=True), strictly preserves real attendee accounts
    and only purges synthetic test accounts to prevent accidental data loss.
    Always creates an emergency persistent backup before any modification.
    """
    SAFE_BACKUP_DIR = DATA_DIR / "players_safe_backup"
    SAFE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    lock_path = str(PLAYERS_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        current_data = read_data(PLAYERS_FILE)
        players = current_data.get("players", {})

        # 1. Always create safe timestamped snapshot if there are any players
        if players:
            ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            try:
                with open(SAFE_BACKUP_DIR / f"players_pre_clear_{ts_str}.json", "w", encoding="utf-8") as f:
                    json.dump(current_data, f, indent=2)
            except Exception as e:
                print(f"[DataManager] Safe backup error: {e}")

        # 2. Determine what to keep
        if keep_real_players and not force:
            retained_players = {}
            for pid, pdata in players.items():
                if not is_test_account(pdata):
                    retained_players[pid] = pdata

            # Update players.json with retained real players
            write_data(PLAYERS_FILE, {"players": retained_players}, backup=False)

            # In PLAYERS_DIR, only remove individual files of deleted test accounts
            if PLAYERS_DIR.exists():
                for f in PLAYERS_DIR.glob("*.json"):
                    stem_id = f.stem
                    if stem_id not in retained_players:
                        try:
                            file_p = read_data(f)
                            if is_test_account(file_p):
                                f.unlink(missing_ok=True)
                                lock_f = PLAYERS_DIR / f"{f.name}.lock"
                                lock_f.unlink(missing_ok=True)
                        except Exception:
                            pass
            return True
        else:
            # Full wipe explicitly forced
            write_data(PLAYERS_FILE, {"players": {}})
            if PLAYERS_DIR.exists():
                for f in PLAYERS_DIR.glob("*"):
                    try:
                        f.unlink(missing_ok=True)
                    except Exception:
                        pass
            return True

def clear_test_players() -> bool:
    """Explicit helper to clean up test accounts while keeping real player profiles intact."""
    return clear_all_players(force=False, keep_real_players=True)

def register_or_get_player(email: str, name: str, starting_balance: int | None = None, newsletter_opt_in: bool = False) -> tuple[dict, bool]:
    """
    Registers a new player or returns the existing player if email matches.
    Returns (player_dict, is_new_player).
    Saves an individual JSON file for the player and updates the main registry.
    """
    import uuid
    if starting_balance is None:
        cfg = get_economy_config()
        starting_balance = int(cfg.get("initial_allotment", 50))

    norm_email = email.strip().lower()
    trimmed_name = name.strip()
    
    lock_path = str(PLAYERS_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        data = read_data(PLAYERS_FILE)
        if "players" not in data:
            data["players"] = {}
            
        # Collect existing pins
        existing_pins = {str(p.get("pin", "")).strip() for p in data["players"].values() if "pin" in p}

        # Check existing by email
        for pid, pdata in data["players"].items():
            if pdata.get("email", "").strip().lower() == norm_email:
                changed = False
                if trimmed_name and pdata.get("name") != trimmed_name:
                    pdata["name"] = trimmed_name
                    changed = True
                if newsletter_opt_in != pdata.get("newsletter_opt_in"):
                    pdata["newsletter_opt_in"] = newsletter_opt_in
                    changed = True
                # Ensure existing has a pin
                if "pin" not in pdata or not pdata.get("pin"):
                    pdata["pin"] = generate_unique_pin(existing_pins)
                    existing_pins.add(pdata["pin"])
                    changed = True
                if changed:
                    write_data(PLAYERS_FILE, data)
                res = dict(pdata)
                res["id"] = pid
                # Save individual JSON
                save_player_file(res)
                return res, False
                
        # Generate new unique player id and 4-digit PIN
        new_id = f"p_{uuid.uuid4().hex[:8]}"
        new_pin = generate_unique_pin(existing_pins)
        new_player = {
            "id": new_id,
            "name": trimmed_name,
            "email": norm_email,
            "pin": new_pin,
            "balance": starting_balance,
            "created_at": int(time.time()),
            "total_wagers": 0,
            "total_winnings": 0,
            "newsletter_opt_in": bool(newsletter_opt_in),
            "updated_at": time.time()
        }
        data["players"][new_id] = new_player
        write_data(PLAYERS_FILE, data)
        
        # Save individual JSON
        save_player_file(new_player)
        
        res = dict(new_player)
        res["id"] = new_id
        return res, True

def adjust_player_balance(player_id: str, amount: int, winnings: int = 0) -> dict | None:
    """
    Adjusts a player balance by delta (positive or negative) and optionally records winnings.
    Operates on the player's individual JSON file with per-player lock to eliminate race conditions
    when 100+ players update simultaneously, then synchronizes to the main players.json registry.
    """
    if not player_id:
        return None
    
    clean_id = str(player_id).strip()
    real_player = get_player(clean_id)
    if not real_player:
        real_player = get_player_by_email(clean_id)
    if not real_player:
        real_player = get_player_by_pin(clean_id)
    if real_player and "id" in real_player:
        clean_id = real_player["id"]

    PLAYERS_DIR.mkdir(parents=True, exist_ok=True)
    pfile = get_player_file(clean_id)
    player_lock = str(pfile) + ".lock"

    with FileLock(player_lock, is_singleton=True):
        p = None
        if pfile.exists():
            try:
                p = read_data(pfile)
            except Exception:
                p = None
        
        # Fallback to main registry if individual file not yet created
        if not p:
            registry_data = read_data(PLAYERS_FILE)
            if "players" in registry_data and clean_id in registry_data["players"]:
                p = dict(registry_data["players"][clean_id])
                p["id"] = clean_id
        
        if not p:
            return None
        
        p["balance"] = max(0, int(p.get("balance", 0)) + amount)
        if winnings > 0:
            p["total_winnings"] = int(p.get("total_winnings", 0)) + winnings
        p["updated_at"] = time.time()
        
        write_data(pfile, p, backup=False)
        res = dict(p)
        res["id"] = clean_id

        # Sync to main registry under player lock
        sync_player_to_registry(res)
        return res

def record_player_winnings(player_id: str, payout: int) -> dict | None:
    """Convenience helper to award payout tokens and record total_winnings atomically."""
    return adjust_player_balance(player_id, payout, winnings=payout)

def reset_all_balances(default_balance: int = 100) -> int:
    """Resets all player balances to default_balance across individual files and players.json."""
    lock_path = str(PLAYERS_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        data = read_data(PLAYERS_FILE)
        count = 0
        for pid, p in data.get("players", {}).items():
            p["balance"] = default_balance
            p["updated_at"] = time.time()
            pfile = get_player_file(pid)
            if pfile.exists() or PLAYERS_DIR.exists():
                try:
                    write_data(pfile, p, backup=False)
                except Exception:
                    pass
            count += 1
        write_data(PLAYERS_FILE, data)
        return count

def get_economy_config() -> dict:
    """Loads and deep-merges the economy configuration with defaults."""
    import copy
    if not ECONOMY_FILE.exists():
        save_economy_config(DEFAULT_ECONOMY_CONFIG)
        return copy.deepcopy(DEFAULT_ECONOMY_CONFIG)
    try:
        data = read_data(ECONOMY_FILE)
        merged = copy.deepcopy(DEFAULT_ECONOMY_CONFIG)
        if isinstance(data, dict):
            if "initial_allotment" in data:
                merged["initial_allotment"] = int(data["initial_allotment"])
            if "tokens_per_dollar" in data:
                merged["tokens_per_dollar"] = max(1, int(data["tokens_per_dollar"]))
            if "costs" in data and isinstance(data["costs"], dict):
                merged["costs"].update({k: int(v) for k, v in data["costs"].items() if isinstance(v, (int, float))})
            if "payouts" in data and isinstance(data["payouts"], dict):
                for k, v in data["payouts"].items():
                    if k == "gauntlet" and isinstance(v, dict):
                        merged["payouts"]["gauntlet"].update({gk: int(gv) for gk, gv in v.items() if isinstance(gv, (int, float))})
                    elif k == "plinko_slots" and isinstance(v, list):
                        merged["payouts"]["plinko_slots"] = [int(x) for x in v if isinstance(x, (int, float))]
                    elif k == "bison_dash_multiplier":
                        merged["payouts"]["bison_dash_multiplier"] = float(v)
                    elif isinstance(v, (int, float)):
                        merged["payouts"][k] = int(v)
            if "timers" in data and isinstance(data["timers"], dict):
                merged.setdefault("timers", {})
                merged["timers"].update({k: int(v) for k, v in data["timers"].items() if isinstance(v, (int, float))})
            elif "bughunt_timer_seconds" in data:
                merged.setdefault("timers", {})["bughunt_duration"] = int(data["bughunt_timer_seconds"])
        return merged
    except Exception as e:
        print(f"[Economy] Error loading economy config: {e}")
        return copy.deepcopy(DEFAULT_ECONOMY_CONFIG)

def save_economy_config(config: dict) -> bool:
    """Atomically saves economy configuration."""
    lock_path = str(ECONOMY_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        write_data(ECONOMY_FILE, config, backup=False)
    return True

def deduct_game_cost(player_id: str, game_name: str) -> dict:
    """
    Checks and deducts token cost for a game session.
    Returns {"allowed": bool, "cost": int, "balance": int, "message": str}.
    """
    cfg = get_economy_config()
    cost = int(cfg.get("costs", {}).get(game_name, 0))
    player = get_player(player_id)
    if not player:
        player = get_player_by_email(player_id)
    if not player:
        player = get_player_by_pin(player_id)
    if not player:
        return {"allowed": False, "cost": cost, "balance": 0, "message": "Player not found"}

    current_bal = player.get("balance", 0)
    if cost <= 0:
        return {"allowed": True, "cost": 0, "balance": current_bal, "message": "Free game"}

    if current_bal < cost:
        return {
            "allowed": False,
            "cost": cost,
            "balance": current_bal,
            "message": f"Insufficient tokens! Need {cost} tokens (Balance: {current_bal})."
        }

    updated = adjust_player_balance(player["id"], -cost)
    new_bal = updated.get("balance", 0) if updated else current_bal - cost
    return {
        "allowed": True,
        "cost": cost,
        "balance": new_bal,
        "message": f"Deducted {cost} tokens. New balance: {new_bal}"
    }

# =========================================================================
# SLIDESHOW & STADIUM SCREEN MANAGEMENT
# =========================================================================

def get_slides_manifest() -> dict:
    """Reads slides manifest file atomically with fallback to default."""
    if not SLIDES_MANIFEST_FILE.exists():
        with open(SLIDES_MANIFEST_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SLIDES_MANIFEST, f, indent=2)
        return copy.deepcopy(DEFAULT_SLIDES_MANIFEST)

    try:
        data = read_data(SLIDES_MANIFEST_FILE)
        if "slides" not in data:
            data["slides"] = copy.deepcopy(DEFAULT_SLIDES_MANIFEST["slides"])
        if "presentation_slides" not in data:
            data["presentation_slides"] = copy.deepcopy(DEFAULT_SLIDES_MANIFEST.get("presentation_slides", []))
        if "default_duration" not in data:
            data["default_duration"] = 10
        if "branding" not in data:
            data["branding"] = copy.deepcopy(DEFAULT_SLIDES_MANIFEST["branding"])
        else:
            for k, v in DEFAULT_SLIDES_MANIFEST["branding"].items():
                if k not in data["branding"]:
                    data["branding"][k] = v
        return data
    except Exception as e:
        print(f"[Slides] Error reading slides manifest: {e}")
        return copy.deepcopy(DEFAULT_SLIDES_MANIFEST)

def save_slides_manifest(manifest: dict) -> bool:
    """Atomically saves slides manifest."""
    manifest["updated_at"] = time.time()
    lock_path = str(SLIDES_MANIFEST_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        write_data(SLIDES_MANIFEST_FILE, manifest, backup=False)
    return True

def process_and_save_slide(file_bytes: bytes, filename: str, title: str = None, deck: str = "regular") -> dict:
    """
    Takes uploaded image bytes, resizes and fits to exactly 1920x1080 (16:9) using high-quality
    LANCZOS resampling on a dark arena background canvas, and persists to static/slides/.
    Appends metadata to either 'slides' (deck='regular') or 'presentation_slides' (deck='presentation').
    """
    from PIL import Image
    import io
    import uuid

    SLIDES_DIR.mkdir(parents=True, exist_ok=True)

    img = Image.open(io.BytesIO(file_bytes))
    img = img.convert("RGB")

    target_w, target_h = 1920, 1080
    orig_w, orig_h = img.size

    # Scale to fit inside 1920x1080 while preserving aspect ratio
    ratio = min(target_w / orig_w, target_h / orig_h)
    new_w, new_h = max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio))

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Dark arena letterbox canvas (#080c14 -> (8, 12, 20))
    canvas = Image.new("RGB", (target_w, target_h), (8, 12, 20))
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y))

    prefix = "pres" if deck == "presentation" else "slide"
    slide_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
    save_filename = f"{slide_id}.jpg"
    save_path = SLIDES_DIR / save_filename

    canvas.save(save_path, "JPEG", quality=92, optimize=True)

    manifest = get_slides_manifest()
    clean_title = title.strip() if (title and title.strip()) else Path(filename).stem.replace("_", " ").title()

    if deck == "presentation":
        pres_list = manifest.setdefault("presentation_slides", [])
        max_order = max([s.get("order", 0) for s in pres_list], default=-1)
        new_slide = {
            "id": slide_id,
            "type": "presentation_image",
            "title": clean_title,
            "filename": save_filename,
            "url": f"/static/slides/{save_filename}",
            "enabled": True,
            "duration": 0,
            "order": max_order + 1,
            "created_at": int(time.time()),
            "width": target_w,
            "height": target_h
        }
        pres_list.append(new_slide)
        save_slides_manifest(manifest)
        print(f"[Slides] Uploaded presentation slide: {clean_title} -> {save_filename} (1920x1080, index {new_slide['order']})")
        return new_slide
    else:
        reg_list = manifest.setdefault("slides", [])
        max_order = max([s.get("order", 0) for s in reg_list], default=-1)
        new_slide = {
            "id": slide_id,
            "type": "custom_image",
            "title": clean_title,
            "filename": save_filename,
            "url": f"/static/slides/{save_filename}",
            "enabled": True,
            "duration": int(manifest.get("default_duration", 10)),
            "order": max_order + 1,
            "created_at": int(time.time()),
            "width": target_w,
            "height": target_h
        }
        reg_list.append(new_slide)
        save_slides_manifest(manifest)
        print(f"[Slides] Uploaded & resized slide: {clean_title} -> {save_filename} (1920x1080)")
        return new_slide

def delete_slide(slide_id: str) -> bool:
    """Removes a slide from the manifest and deletes image file if custom."""
    manifest = get_slides_manifest()
    slide_to_remove = None
    remaining = []

    for s in manifest.get("slides", []):
        if s.get("id") == slide_id:
            slide_to_remove = s
        else:
            remaining.append(s)

    if not slide_to_remove:
        return False

    # Delete image file from static/slides if it's a custom uploaded image
    filename = slide_to_remove.get("filename")
    if filename:
        file_path = SLIDES_DIR / filename
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"[Slides] Removed file {filename}")
            except Exception as e:
                print(f"[Slides] Error removing file {filename}: {e}")

    # Re-index orders cleanly
    for idx, s in enumerate(remaining):
        s["order"] = idx

    manifest["slides"] = remaining
    save_slides_manifest(manifest)
    return True

def toggle_slide(slide_id: str, enabled: bool) -> bool:
    """Toggles enabled status of a slide in the deck."""
    manifest = get_slides_manifest()
    found = False
    for s in manifest.get("slides", []):
        if s.get("id") == slide_id:
            s["enabled"] = bool(enabled)
            found = True
            break
    if found:
        save_slides_manifest(manifest)
    return found

def reorder_slides(slide_ids: list) -> bool:
    """Reorders slides according to the provided list of IDs."""
    manifest = get_slides_manifest()
    id_to_slide = {s.get("id"): s for s in manifest.get("slides", [])}
    new_slides = []

    for idx, sid in enumerate(slide_ids):
        if sid in id_to_slide:
            slide = id_to_slide[sid]
            slide["order"] = idx
            new_slides.append(slide)

    # Append any unmentioned slides at the end
    for s in manifest.get("slides", []):
        if s.get("id") not in slide_ids:
            s["order"] = len(new_slides)
            new_slides.append(s)

    manifest["slides"] = new_slides
    save_slides_manifest(manifest)
    return True

def get_presentation_slides() -> list:
    """Returns presentation slides sorted by order."""
    manifest = get_slides_manifest()
    return sorted(manifest.get("presentation_slides", []), key=lambda s: s.get("order", 0))

def delete_presentation_slide(slide_id: str) -> bool:
    """Removes a slide from the presentation deck and deletes image file."""
    manifest = get_slides_manifest()
    slide_to_remove = None
    remaining = []

    for s in manifest.get("presentation_slides", []):
        if s.get("id") == slide_id:
            slide_to_remove = s
        else:
            remaining.append(s)

    if not slide_to_remove:
        return False

    filename = slide_to_remove.get("filename")
    if filename:
        file_path = SLIDES_DIR / filename
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"[Slides] Removed presentation file {filename}")
            except Exception as e:
                print(f"[Slides] Error removing presentation file {filename}: {e}")

    for idx, s in enumerate(remaining):
        s["order"] = idx

    manifest["presentation_slides"] = remaining
    save_slides_manifest(manifest)
    return True

def reorder_presentation_slides(slide_ids: list) -> bool:
    """Reorders presentation slides according to the provided list of IDs."""
    manifest = get_slides_manifest()
    id_to_slide = {s.get("id"): s for s in manifest.get("presentation_slides", [])}
    new_slides = []

    for idx, sid in enumerate(slide_ids):
        if sid in id_to_slide:
            slide = id_to_slide[sid]
            slide["order"] = idx
            new_slides.append(slide)

    for s in manifest.get("presentation_slides", []):
        if s.get("id") not in slide_ids:
            s["order"] = len(new_slides)
            new_slides.append(s)

    manifest["presentation_slides"] = new_slides
    save_slides_manifest(manifest)
    return True

# --- Slideshow Branding, Logo & Header Toggles ---

STATIC_IMG_DIR = Path("master_admin/static/img")
STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)

def get_slideshow_branding() -> dict:
    """Returns current slideshow branding and header toggle configurations."""
    manifest = get_slides_manifest()
    return manifest.get("branding", DEFAULT_SLIDES_MANIFEST["branding"])

def set_slideshow_branding(show_header_title: bool = True, show_clock: bool = True) -> dict:
    """Sets visibility toggles for the Techlahoma header and live clock pill."""
    manifest = get_slides_manifest()
    branding = manifest.setdefault("branding", copy.deepcopy(DEFAULT_SLIDES_MANIFEST["branding"]))
    branding["show_header_title"] = bool(show_header_title)
    branding["show_clock"] = bool(show_clock)
    save_slides_manifest(manifest)
    print(f"[Slideshow] Updated branding toggles: title={show_header_title}, clock={show_clock}")
    return branding

def save_custom_logo(file_bytes: bytes, filename: str) -> dict:
    """
    Saves an uploaded PNG/image as the 100x100 stadium logo.
    Fits cleanly inside a 100x100 RGBA transparent canvas.
    """
    from PIL import Image
    import io

    STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(file_bytes)).convert("RGBA")

    target_w, target_h = 100, 100
    orig_w, orig_h = img.size
    ratio = min(target_w / orig_w, target_h / orig_h)
    new_w, new_h = max(1, int(orig_w * ratio)), max(1, int(orig_h * ratio))

    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y), mask=resized)

    save_path = STATIC_IMG_DIR / "bison_logo.png"
    canvas.save(save_path, "PNG", optimize=True)

    manifest = get_slides_manifest()
    branding = manifest.setdefault("branding", copy.deepcopy(DEFAULT_SLIDES_MANIFEST["branding"]))
    branding["logo_url"] = f"/static/img/bison_logo.png?v={int(time.time())}"
    save_slides_manifest(manifest)
    print(f"[Slideshow] Saved custom 100x100 logo: {filename} -> {save_path}")
    return branding

def reset_custom_logo() -> dict:
    """Resets the stadium logo back to default official logo."""
    STATIC_IMG_DIR.mkdir(parents=True, exist_ok=True)
    placeholder_path = STATIC_IMG_DIR / "bison_placeholder.png"
    save_path = STATIC_IMG_DIR / "bison_logo.png"
    if placeholder_path.exists():
        import shutil
        shutil.copyfile(placeholder_path, save_path)

    manifest = get_slides_manifest()
    branding = manifest.setdefault("branding", copy.deepcopy(DEFAULT_SLIDES_MANIFEST["branding"]))
    branding["logo_url"] = f"/static/img/bison_logo.png?v={int(time.time())}"
    save_slides_manifest(manifest)
    return branding

# =========================================================================
# BISON DASH & PRESENTATION MANUAL CUT-IN & STATE
# =========================================================================

def get_slideshow_state() -> dict:
    """Reads current slideshow projector mode and race countdown state."""
    if not SLIDESHOW_STATE_FILE.exists():
        with open(SLIDESHOW_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SLIDESHOW_STATE, f, indent=2)
        return copy.deepcopy(DEFAULT_SLIDESHOW_STATE)

    try:
        data = read_data(SLIDESHOW_STATE_FILE)
        if "mode" not in data:
            data["mode"] = "slideshow"
        if "countdown" not in data:
            data["countdown"] = copy.deepcopy(DEFAULT_SLIDESHOW_STATE["countdown"])
        if "presentation" not in data:
            data["presentation"] = copy.deepcopy(DEFAULT_SLIDESHOW_STATE["presentation"])
        if "restart_trigger" not in data:
            data["restart_trigger"] = 0
        data["manifest_updated_at"] = get_slides_manifest().get("updated_at", 0)
        return data
    except Exception as e:
        print(f"[Slideshow State] Error reading state: {e}")
        return copy.deepcopy(DEFAULT_SLIDESHOW_STATE)

def save_slideshow_state(state: dict) -> bool:
    """Atomically saves slideshow state."""
    lock_path = str(SLIDESHOW_STATE_FILE) + ".lock"
    with FileLock(lock_path, is_singleton=True):
        write_data(SLIDESHOW_STATE_FILE, state, backup=False)
    return True

def set_slideshow_countdown(minutes: float = 0, seconds: int = 0, title: str = None) -> dict:
    """
    Manually triggers the 'Time left till race' countdown slide on the stadium projector.
    """
    total_sec = max(5, int(minutes * 60 + seconds))
    now = time.time()
    state = get_slideshow_state()
    state["mode"] = "bison_countdown"
    state["countdown"] = {
        "active": True,
        "duration_seconds": total_sec,
        "target_timestamp": now + total_sec,
        "title": title or "Next Bison Dash Race",
        "started_at": now
    }
    state["presentation"]["active"] = False
    save_slideshow_state(state)
    print(f"[Slideshow] Bison Dash Countdown activated: {total_sec}s ({minutes}m {seconds}s) - '{title}'")
    return state

def stop_slideshow_countdown() -> dict:
    """Stops countdown slide and returns projector to the regular slideshow rotation."""
    state = get_slideshow_state()
    state["mode"] = "slideshow"
    state["countdown"]["active"] = False
    state["presentation"]["active"] = False
    save_slideshow_state(state)
    print("[Slideshow] Returned to regular slideshow rotation.")
    return state

def set_slideshow_mode(mode: str) -> dict:
    """Directly sets projector mode ('slideshow', 'bison_countdown', 'bison_prerace', 'bison_race', 'presentation')."""
    valid_modes = {"slideshow", "bison_countdown", "bison_prerace", "bison_race", "presentation"}
    if mode not in valid_modes:
        mode = "slideshow"
    state = get_slideshow_state()
    state["mode"] = mode
    if mode == "slideshow":
        state["countdown"]["active"] = False
        state["presentation"]["active"] = False
    elif mode == "presentation":
        state["countdown"]["active"] = False
        state["presentation"]["active"] = True
    elif mode.startswith("bison_"):
        state["presentation"]["active"] = False
    save_slideshow_state(state)
    print(f"[Slideshow] Projector mode switched to: {mode}")
    return state

def start_presentation_mode(slide_index: int = 0) -> dict:
    """Starts stage presentation cut-in mode at the specified slide index."""
    state = get_slideshow_state()
    slides = get_presentation_slides()
    total = len(slides)
    idx = max(0, min(slide_index, total - 1)) if total > 0 else 0

    state["mode"] = "presentation"
    state["countdown"]["active"] = False
    state["presentation"] = {
        "active": True,
        "current_index": idx,
        "title": "Stage Presentation"
    }
    save_slideshow_state(state)
    print(f"[Slideshow] Presentation Cut-In activated at slide #{idx + 1} of {total}")
    return state

def stop_presentation_mode() -> dict:
    """Stops presentation cut-in mode and returns projector to regular slideshow rotation."""
    state = get_slideshow_state()
    state["mode"] = "slideshow"
    state["presentation"]["active"] = False
    state["countdown"]["active"] = False
    save_slideshow_state(state)
    print("[Slideshow] Presentation Cut-In deactivated. Returned to regular rotation.")
    return state

def step_presentation_slide(delta: int = 1) -> dict:
    """Steps to the next (delta=+1) or previous (delta=-1) presentation slide."""
    state = get_slideshow_state()
    slides = get_presentation_slides()
    total = len(slides)
    cur = state.get("presentation", {}).get("current_index", 0)

    if total > 0:
        new_idx = max(0, min(cur + delta, total - 1))
    else:
        new_idx = 0

    state["mode"] = "presentation"
    state["presentation"]["active"] = True
    state["presentation"]["current_index"] = new_idx
    save_slideshow_state(state)
    print(f"[Slideshow] Presentation slide changed to {new_idx + 1}/{total}")
    return state

def set_presentation_slide_index(index: int) -> dict:
    """Directly sets presentation slide to a specific index."""
    state = get_slideshow_state()
    slides = get_presentation_slides()
    total = len(slides)
    if total > 0:
        idx = max(0, min(index, total - 1))
    else:
        idx = 0
    state["mode"] = "presentation"
    state["presentation"]["active"] = True
    state["presentation"]["current_index"] = idx
    save_slideshow_state(state)
    return state

def restart_regular_slideshow() -> dict:
    """
    Instantly returns projector to the regular slideshow rotation from beginning.
    Stops countdowns, stops presentation, resets slide index, and broadcasts restart_trigger timestamp.
    """
    state = get_slideshow_state()
    state["mode"] = "slideshow"
    state["countdown"]["active"] = False
    state["presentation"]["active"] = False
    state["presentation"]["current_index"] = 0
    state["restart_trigger"] = time.time()
    save_slideshow_state(state)
    print("[Slideshow] RESTART REGULAR SLIDESHOW triggered. Returning to regular deck slide 0.")
    return state

# --- Finalized Links & QR Operations ---

def get_finalized_links() -> list:
    """Returns the list of finalized event links, initializing defaults if needed."""
    if not FINALIZED_LINKS_FILE.exists():
        save_finalized_links(DEFAULT_FINALIZED_LINKS)
        return copy.deepcopy(DEFAULT_FINALIZED_LINKS)
    try:
        data = read_data(FINALIZED_LINKS_FILE)
        if isinstance(data, dict) and "links" in data:
            return data["links"]
        elif isinstance(data, list):
            return data
        return copy.deepcopy(DEFAULT_FINALIZED_LINKS)
    except Exception as e:
        print(f"Error loading finalized links: {e}")
        return copy.deepcopy(DEFAULT_FINALIZED_LINKS)

def save_finalized_links(links: list) -> list:
    """Saves the finalized links array atomically."""
    write_data(FINALIZED_LINKS_FILE, {"links": links})
    return links

def save_or_update_link(link_dict: dict) -> list:
    """Updates an existing link or appends a new custom finalized link."""
    links = get_finalized_links()
    link_id = link_dict.get("id")
    if not link_id:
        link_id = f"custom_{int(time.time())}"
        link_dict["id"] = link_id
        link_dict["is_custom"] = True

    found = False
    for i, l in enumerate(links):
        if l.get("id") == link_id:
            links[i].update(link_dict)
            found = True
            break

    if not found:
        links.append(link_dict)

    save_finalized_links(links)
    return links

def delete_finalized_link(link_id: str) -> bool:
    """Deletes a custom link from finalized links list."""
    links = get_finalized_links()
    initial_len = len(links)
    links = [l for l in links if l.get("id") != link_id]
    if len(links) < initial_len:
        save_finalized_links(links)
        return True
    return False


