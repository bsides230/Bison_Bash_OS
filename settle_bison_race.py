#!/usr/bin/env python3
"""
settle_bison_race.py

CLI tool to pay out winning bison bets and clear the active wagers ledger for the next race.
Follows the KISS principle — completely decoupled from the arena simulator.
"""

import sys
import argparse
from pathlib import Path

# Fix Windows console encoding for Unicode/emoji
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import master_admin.bison_ledger as ledger

BISON_NAMES = {
    1: "Thunder Stampede",
    2: "Cyber Steer",
    3: "Prairie Rocket",
    4: "Iron Horn",
    5: "Neon Goliath",
    6: "Solar Flare"
}

def main():
    parser = argparse.ArgumentParser(description="Settle Bison Dash race wagers & pay out winners.")
    parser.add_argument("slot", nargs="?", type=int, help="Winning bison slot number (1-6)")
    parser.add_argument("--winner", "-w", type=int, dest="opt_slot", help="Winning bison slot number (1-6)")
    parser.add_argument("--status", "-s", action="store_true", help="View current active wagers without settling")
    parser.add_argument("--clear", "-c", action="store_true", help="Clear active wagers without paying out")
    parser.add_argument("--multiplier", "-m", type=float, default=2.0, help="Payout multiplier (default 2.0)")

    args = parser.parse_args()

    wagers = ledger.get_all_active_wagers()

    if args.status:
        print("\n=== BISON DASH: ACTIVE WAGERS LEDGER ===")
        if not wagers:
            print("No active wagers placed yet for the upcoming race.")
        else:
            total_pot = sum(w.get("amount", 0) for w in wagers)
            print(f"Total Wagers: {len(wagers)} | Total Pot: {total_pot} Tokens 🪙\n")
            for i, w in enumerate(wagers, 1):
                print(f"  {i}. {w.get('player_name')} (PIN: {w.get('pin')}) -> {w.get('amount')} Tokens on Slot {w.get('slot')} ({w.get('bison_name')})")
        print("=========================================\n")
        return

    if args.clear:
        count = ledger.clear_active_wagers()
        print(f"\n[RESET] Cleared {count} active wagers. Ledger is now empty for the next race.\n")
        return

    slot = args.slot or args.opt_slot

    if slot is None:
        print("\n" + "="*50)
        print("   BISON DASH RACE SETTLEMENT & PAYOUT CONSOLE")
        print("="*50)
        total_pot = sum(w.get("amount", 0) for w in wagers)
        print(f"Active wagers in ledger: {len(wagers)} | Total Pot: {total_pot} Tokens 🪙")
        if wagers:
            for w in wagers:
                print(f"  • {w.get('player_name')}: {w.get('amount')} Tokens on Slot {w.get('slot')} ({w.get('bison_name')})")
        print("\nSelect the winning bison:")
        for s in range(1, 7):
            print(f"  [{s}] Slot {s} - {BISON_NAMES.get(s)}")
        
        try:
            choice = input("\nEnter winning bison slot (1-6) [or 'q' to quit]: ").strip()
            if choice.lower() in ['q', 'quit', 'exit']:
                print("Settlement cancelled.")
                return
            slot = int(choice)
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            return

    if slot < 1 or slot > 6:
        print(f"Error: Invalid slot {slot}. Must be between 1 and 6.")
        sys.exit(1)

    winner_name = BISON_NAMES.get(slot, f"Slot {slot}")
    print(f"\n---> Settling race for WINNER: Slot {slot} ({winner_name}) at {args.multiplier}x payout...")

    result = ledger.settle_race(slot, multiplier=args.multiplier)

    print("\n" + "="*50)
    print(f"🎉 RACE SETTLED SUCCESSFULLY! WINNER: SLOT {slot} ({winner_name})")
    print(f"Total Wagers Processed: {result['total_wagers']}")
    print(f"Total Paid Out: {result['total_paid_out']} Tokens 🪙")
    print("="*50)

    if result['winners']:
        print("\nWINNING PAYOUTS CREDITED:")
        for win in result['winners']:
            print(f"  ✓ {win['player_name']} (PIN: {win.get('pin')}): Bet {win['bet_amount']} -> WON {win['win_payout']} TOKENS (New Balance: {win.get('new_balance')})")
    else:
        print("\nNo players bet on the winning bison for this race.")

    if result['losers']:
        print(f"\nNon-winning wagers: {len(result['losers'])}")

    print(f"\n✓ bison_active_wagers.json CLEARED. Betting is now OPEN for the next race!\n")

if __name__ == "__main__":
    main()
