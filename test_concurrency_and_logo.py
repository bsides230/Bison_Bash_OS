import concurrent.futures
import time
import os
from pathlib import Path
from PIL import Image
import master_admin.data_manager as dm

def run_tests():
    print("==================================================")
    print(" RUNNING 100-PLAYER CONCURRENCY & LOGO PERMANENCE ")
    print("==================================================")

    # 1. VERIFY PERMANENT LOGO & NO OVERWRITE ON RESET
    print("\n--- 1. Testing Permanent Cyber Bison Logo ---")
    logo_path = dm.STATIC_IMG_DIR / "bison_logo.png"
    placeholder_path = dm.STATIC_IMG_DIR / "bison_placeholder.png"

    assert logo_path.exists(), f"bison_logo.png does not exist at {logo_path}"
    assert placeholder_path.exists(), f"bison_placeholder.png does not exist at {placeholder_path}"

    with Image.open(logo_path) as img:
        assert img.size == (100, 100), f"Logo size must be (100, 100), got {img.size}"
        assert img.mode == "RGBA", f"Logo mode must be RGBA, got {img.mode}"

    # Verify reset_custom_logo() preserves the official cyber bison logo
    initial_bytes = logo_path.read_bytes()
    dm.reset_custom_logo()
    post_reset_bytes = logo_path.read_bytes()
    assert post_reset_bytes == initial_bytes, "reset_custom_logo() overwrote official logo with a placeholder!"
    print("  [PASS] Permanent 100x100 Cyber Bison Logo verified; immune to reset overwrites.")

    # 2. AUDIT TEMPLATES FOR BISON LOGO INTEGRATION
    print("\n--- 2. Auditing Templates for Bison Emoji -> Logo Replacement ---")
    templates_to_check = [
        ("Slideshow HUD & Countdown Runner", "master_admin/templates/slideshow.html"),
        ("Admin Dashboard Top Bar", "master_admin/templates/dashboard.html"),
        ("Bison Dash MC Flight Deck", "game_hub/games/bison_dash/templates/admin.html"),
        ("Bison Dash Kiosk Betting Station", "game_hub/games/bison_dash/templates/kiosk.html"),
        ("Mobile Player Portal Header", "game_hub/games/bison_dash/templates/portal.html"),
        ("Racer Workshop Screen", "game_hub/games/bison_dash/templates/bison.html"),
        ("Bison Dash Arena Tab", "game_hub/admin/templates/bisondash_tab.html"),
    ]

    for label, path_str in templates_to_check:
        content = Path(path_str).read_text(encoding="utf-8")
        assert "bison_logo.png" in content, f"{label} ({path_str}) missing bison_logo.png image reference!"
        print(f"  [PASS] {label} verified with bison_logo.png.")

    # 3. VERIFY INDIVIDUAL PLAYER JSON STORAGE ARCHITECTURE
    print("\n--- 3. Testing Individual Player JSON Architecture ---")
    dm.clear_test_players()
    assert dm.PLAYERS_DIR.exists()

    # Register 5 players
    players = []
    for i in range(5):
        p, is_new = dm.register_or_get_player(f"user{i}@test.com", f"Player_{i}", starting_balance=100)
        assert is_new is True
        pfile = dm.get_player_file(p["id"])
        assert pfile.exists(), f"Player individual JSON {pfile} was not created!"
        players.append(p)

    print(f"  [PASS] Created 5 players with individual JSON files in {dm.PLAYERS_DIR}.")

    # 4. RUN MASSIVE 100-PLAYER CONCURRENT BALANCE UPDATES
    print("\n--- 4. Testing 100 Concurrent Players (Anti-Race Condition) ---")
    dm.clear_test_players()

    NUM_PLAYERS = 100
    UPDATES_PER_PLAYER = 10
    DELTA_PER_UPDATE = 5

    print(f"  Registering {NUM_PLAYERS} individual attendee accounts...")
    all_players = []
    for i in range(NUM_PLAYERS):
        p, _ = dm.register_or_get_player(f"attendee_{i:03d}@venue.com", f"Attendee_{i:03d}", starting_balance=100)
        all_players.append(p)

    assert len(all_players) == NUM_PLAYERS
    # Verify each player has an individual JSON file
    for p in all_players:
        pfile = dm.get_player_file(p["id"])
        assert pfile.exists(), f"Missing file for {p['id']}"

    print(f"  [PASS] All {NUM_PLAYERS} player JSON files created.")

    # Execute concurrent balance adjustments across all 100 players simultaneously
    print(f"  Firing {NUM_PLAYERS * UPDATES_PER_PLAYER} concurrent balance updates across multiple worker threads...")

    def update_task(player_id, amount, win):
        return dm.adjust_player_balance(player_id, amount, winnings=win)

    tasks = []
    # Mix of credits (+5) and debits (-2) for each player
    # Net change per update: +3. Total net change after 10 updates: +30 (100 -> 130).
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        for _ in range(UPDATES_PER_PLAYER):
            for p in all_players:
                tasks.append(executor.submit(update_task, p["id"], 5, 5))
                tasks.append(executor.submit(update_task, p["id"], -2, 0))

        # Await completion
        for future in concurrent.futures.as_completed(tasks):
            res = future.result()
            assert res is not None

    print(f"  [PASS] All {len(tasks)} concurrent balance adjustments executed.")

    # 5. VERIFY ZERO RACE CONDITIONS: 100% MATHEMATICAL PRECISION
    print("\n--- 5. Verifying Zero Race Conditions & 100% State Consistency ---")
    # Expected final balance: 100 + (5 - 2) * 10 = 130
    # Expected total_winnings: 5 * 10 = 50
    expected_balance = 100 + (5 - 2) * UPDATES_PER_PLAYER
    expected_winnings = 5 * UPDATES_PER_PLAYER

    # 5a. Verify individual player files
    for p in all_players:
        pid = p["id"]
        pfile = dm.get_player_file(pid)
        assert pfile.exists()
        p_data = dm.read_data(pfile)
        assert p_data["balance"] == expected_balance, f"Player {pid} individual file balance mismatch! Expected {expected_balance}, got {p_data['balance']}"
        assert p_data.get("total_winnings") == expected_winnings, f"Player {pid} total_winnings mismatch! Expected {expected_winnings}, got {p_data.get('total_winnings')}"

    print(f"  [PASS] All {NUM_PLAYERS} individual player JSON files match exact balance ({expected_balance}) and winnings ({expected_winnings}).")

    # 5b. Verify main players.json registry matches individual files exactly
    registry = dm.read_data(dm.PLAYERS_FILE).get("players", {})
    attendee_pids = {p["id"] for p in all_players}
    test_registry = {pid: p for pid, p in registry.items() if pid in attendee_pids}
    assert len(test_registry) == NUM_PLAYERS, f"Registry count mismatch: expected {NUM_PLAYERS}, got {len(test_registry)}"

    for p in all_players:
        pid = p["id"]
        assert pid in registry, f"Player {pid} missing from main registry!"
        assert registry[pid]["balance"] == expected_balance, f"Registry balance mismatch for {pid}: expected {expected_balance}, got {registry[pid]['balance']}"
        assert registry[pid]["total_winnings"] == expected_winnings, f"Registry winnings mismatch for {pid}: expected {expected_winnings}, got {registry[pid]['total_winnings']}"

    print(f"  [PASS] Main leaderboard/registry players.json is 100% synchronized with individual player JSONs.")

    # 5c. Test rebuild_registry_from_player_files()
    recompiled = dm.rebuild_registry_from_player_files()
    assert all(pid in recompiled for pid in attendee_pids), "Not all attendees found in recompiled registry"
    print("  [PASS] rebuild_registry_from_player_files() verified.")

    # 6. VERIFY RESET ALL BALANCES
    print("\n--- 6. Testing reset_all_balances ---")
    reset_count = dm.reset_all_balances(100)
    assert reset_count >= NUM_PLAYERS
    for p in all_players:
        check = dm.get_player(p["id"])
        assert check["balance"] == 100

    print("  [PASS] reset_all_balances updated all individual files and registry to 100.")

    # Cleanup
    dm.clear_test_players()
    print("\n==================================================")
    print(" ALL CONCURRENCY & LOGO TESTS PASSED 100%!       ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
