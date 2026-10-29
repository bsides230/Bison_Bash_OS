"""
master_admin/bison_ledger.py

Self-contained, JSON-backed wagering ledger for Bison Dash.
Decoupled completely from the arena animation engine (KISS principle).
"""

import json
from pathlib import Path
from datetime import datetime
import threading
import master_admin.data_manager as dm

DATA_DIR = Path("master_admin/data")
WAGERS_FILE = DATA_DIR / "bison_active_wagers.json"
HISTORY_FILE = DATA_DIR / "bison_race_history.json"

_ledger_lock = threading.RLock()


def _ensure_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WAGERS_FILE.exists():
        with open(WAGERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"wagers": []}, f, indent=2)


def get_all_active_wagers() -> list[dict]:
    with _ledger_lock:
        _ensure_file()
        try:
            with open(WAGERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("wagers", [])
        except Exception:
            return []


def get_wager_for_player(identifier: str) -> dict | None:
    """Check if a player (by id, pin, or email) already placed a bet for the active race."""
    if not identifier:
        return None
    ident_str = str(identifier).strip().lower()
    wagers = get_all_active_wagers()
    for w in wagers:
        if (str(w.get("player_id", "")).strip().lower() == ident_str or
            str(w.get("pin", "")).strip() == ident_str or
            str(w.get("email", "")).strip().lower() == ident_str):
            return w
    return None


def place_wager(player_id: str, slot: int, amount: int, bison_name: str = "") -> tuple[bool, str, dict]:
    """Validates player, checks existing wager, deducts tokens, and appends to bison_active_wagers.json."""
    with _ledger_lock:
        _ensure_file()

        # 1. Resolve player
        player = dm.get_player(player_id)
        if not player:
            player = dm.get_player_by_pin(player_id)
        if not player:
            player = dm.get_player_by_email(player_id)
        if not player:
            return False, "Player account not found.", {}

        pid = player.get("id")
        pin = player.get("pin")
        name = player.get("name") or player.get("display_name") or "Player"
        balance = player.get("balance", 0)

        # 2. Check if player already bet for this race
        existing = get_wager_for_player(pid)
        if not existing and pin:
            existing = get_wager_for_player(pin)
        if existing:
            return False, f"{name} already placed a bet on Slot {existing.get('slot')} ({existing.get('bison_name')}).", existing

        # 3. Validate bet amount
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            return False, "Invalid wager amount.", {}

        if amount < 1:
            return False, "Minimum wager is 1 token.", {}
        if balance < amount:
            return False, f"Insufficient tokens. Available: {balance}, Bet: {amount}", {}

        # 4. Deduct tokens from player's balance atomically
        updated = dm.adjust_player_balance(pid, -amount)
        new_balance = updated.get("balance") if updated else (balance - amount)

        # 5. Record wager in JSON ledger
        wager_entry = {
            "player_id": pid,
            "pin": pin,
            "email": player.get("email"),
            "player_name": name,
            "slot": int(slot),
            "bison_name": bison_name or f"Slot {slot}",
            "amount": amount,
            "timestamp": datetime.now().isoformat()
        }

        try:
            with open(WAGERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"wagers": []}

        data.setdefault("wagers", []).append(wager_entry)

        with open(WAGERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return True, "Wager locked in successfully!", {
            "wager": wager_entry,
            "new_balance": new_balance
        }


def settle_race(winner_slot: int, multiplier: float = 2.0) -> dict:
    """Pays out winning wagers, saves history, and clears the active wagers ledger for the next race."""
    with _ledger_lock:
        _ensure_file()
        wagers = get_all_active_wagers()

        winner_slot = int(winner_slot)
        winners = []
        losers = []
        total_paid_out = 0

        for w in wagers:
            w_slot = int(w.get("slot", 0))
            amt = int(w.get("amount", 0))
            pid = w.get("player_id")
            name = w.get("player_name")

            if w_slot == winner_slot:
                win_amt = int(amt * multiplier)
                net_win = max(0, win_amt - amt)
                updated = dm.adjust_player_balance(pid, win_amt, winnings=net_win)
                new_bal = updated.get("balance") if updated else None

                winners.append({
                    "player_id": pid,
                    "player_name": name,
                    "pin": w.get("pin"),
                    "slot": w_slot,
                    "bison_name": w.get("bison_name"),
                    "bet_amount": amt,
                    "win_payout": win_amt,
                    "new_balance": new_bal
                })
                total_paid_out += win_amt
            else:
                losers.append({
                    "player_id": pid,
                    "player_name": name,
                    "pin": w.get("pin"),
                    "slot": w_slot,
                    "bison_name": w.get("bison_name"),
                    "bet_amount": amt
                })

        # Save to history file
        history_entry = {
            "settled_at": datetime.now().isoformat(),
            "winner_slot": winner_slot,
            "multiplier": multiplier,
            "total_wagers": len(wagers),
            "total_paid_out": total_paid_out,
            "winners": winners,
            "losers": losers
        }

        try:
            history = []
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            history.append(history_entry)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

        # Clear active wagers ledger for next race so players can bet again
        with open(WAGERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"wagers": []}, f, indent=2)

        return {
            "success": True,
            "winner_slot": winner_slot,
            "multiplier": multiplier,
            "total_wagers": len(wagers),
            "winners_count": len(winners),
            "losers_count": len(losers),
            "total_paid_out": total_paid_out,
            "winners": winners,
            "losers": losers
        }


def clear_active_wagers() -> int:
    """Force clears active wagers without settling (e.g. admin reset)."""
    with _ledger_lock:
        wagers = get_all_active_wagers()
        count = len(wagers)
        with open(WAGERS_FILE, "w", encoding="utf-8") as f:
            json.dump({"wagers": []}, f, indent=2)
        return count
