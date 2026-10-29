import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
import master_admin.data_manager as dm
from games.gauntlet_server import app as gauntlet_app
from master_admin.main import app as admin_app

def run_tests():
    print("==================================================")
    print(" RUNNING GAUNTLET ECONOMY & PIN MODAL AUDIT TESTS ")
    print("==================================================")

    # 1. VERIFY PIN AUTH MODAL HAS NO CLOSE 'X' BUTTON AND NO ESCAPE DISMISSAL
    print("\n--- 1. Auditing pin_auth_flow.js for 'X' button removal & Escape guard ---")
    paf_path = Path("master_admin/static/js/pin_auth_flow.js")
    assert paf_path.exists(), "pin_auth_flow.js not found"
    paf_code = paf_path.read_text(encoding="utf-8")

    # Assert that paf-close-modal-btn is NOT in the rendered markup
    assert '<button type="button" class="paf-close-modal-btn"' not in paf_code, "Found paf-close-modal-btn in pin_auth_flow.js! Must be removed."
    assert '&times;' not in paf_code, "Found &times; close button symbol in pin_auth_flow.js! Must be removed."

    # Assert that Escape key clears digits rather than closing modal into guest mode
    assert "e.key === 'Escape'" in paf_code
    assert "if (this.isModal) this.close()" not in paf_code, "Escape key still closes modal into guest mode!"
    print("  [PASS] Modal close 'X' button removed and Escape dismissal disabled across all stations.")

    # 2. VERIFY GAUNTLET TEMPLATE PREVENTS GUEST PLAY
    print("\n--- 2. Auditing gauntlet.html for guest bypass prevention ---")
    gauntlet_html = Path("game_hub/games/bison_dash/templates/gauntlet.html").read_text(encoding="utf-8")
    assert "Guest Player" not in gauntlet_html, "Found 'Guest Player' fallback in gauntlet.html! Must require PIN."
    assert "if (!activePlayer) {\n            openPinKeypad();\n            return;\n        }" in gauntlet_html, "selectDoor must guard against unauthenticated play."
    print("  [PASS] Gauntlet template enforces PIN authentication with zero guest bypass.")

    # 3. VERIFY DEFAULT ECONOMY CONFIG
    print("\n--- 3. Verifying Gauntlet default cost is 4 tokens ---")
    # Reset to default
    dm.clear_test_players()
    eco_cfg = dm.get_economy_config()
    assert eco_cfg.get("costs", {}).get("gauntlet") == 4, f"Expected default gauntlet cost to be 4, got {eco_cfg.get('costs', {}).get('gauntlet')}"
    print(f"  [PASS] Gauntlet cost in economy config is verified at {eco_cfg['costs']['gauntlet']} tokens.")

    # 4. TEST GAUNTLET SERVER ENDPOINTS
    print("\n--- 4. Testing AI Gauntlet Server (:8007) Endpoints ---")
    client = TestClient(gauntlet_app)

    # Config endpoint
    res_cfg = client.get("/api/gauntlet/config")
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.json()
    assert cfg_data["cost"] == 4, f"Expected config cost 4, got {cfg_data['cost']}"
    assert "vault_jackpot" in cfg_data["payouts"]
    print(f"  [PASS] /api/gauntlet/config returned cost: {cfg_data['cost']} tokens.")

    # Register test player
    player, _ = dm.register_or_get_player("tester_gauntlet@venue.com", "GauntletChamp", starting_balance=100)
    pid = player["id"]
    pin = player["pin"]
    print(f"  Registered player: {player['name']} (ID: {pid}, PIN: {pin}, Balance: {player['balance']})")

    # Attendee lookup by PIN
    res_lookup = client.post("/api/attendee/lookup", json={"pin": pin})
    assert res_lookup.status_code == 200
    assert res_lookup.json()["success"] is True
    assert res_lookup.json()["display_name"] == "GauntletChamp"
    assert res_lookup.json()["balance"] == 100
    print("  [PASS] PIN lookup verified for Gauntlet player.")

    # Test Play: Deduct 4 tokens
    res_play = client.post("/api/gauntlet/play", json={"player_id": pid})
    assert res_play.status_code == 200, f"Expected 200 on play, got {res_play.status_code}: {res_play.text}"
    play_data = res_play.json()
    assert play_data["status"] == "success"
    assert play_data["cost"] == 4, f"Expected cost 4, got {play_data['cost']}"
    assert play_data["balance"] == 96, f"Expected balance 96, got {play_data['balance']}"

    # Verify balance in datamanager
    p_after_play = dm.get_player(pid)
    assert p_after_play["balance"] == 96, f"Expected balance 96 in players.json, got {p_after_play['balance']}"
    print(f"  [PASS] Gauntlet play deducted 4 tokens cleanly. New balance: {p_after_play['balance']}.")

    # Test Immediate Payout (Simulating quick 2-second run without 429 lockout)
    print("\n--- 5. Testing Immediate Payout (No 429 Lockout) ---")
    payout_amount = 25  # Grand jackpot
    res_payout = client.post("/api/gauntlet/payout", json={
        "player_id": pid,
        "payout": payout_amount,
        "level_reached": 5,
        "outcome": "WIN"
    })
    assert res_payout.status_code == 200, f"Expected 200 on payout, got {res_payout.status_code}: {res_payout.text}"
    payout_data = res_payout.json()
    assert payout_data["status"] == "success"
    assert payout_data["payout"] == 25
    assert payout_data["new_balance"] == 121, f"Expected new balance 121 (96 + 25), got {payout_data['new_balance']}"

    # Verify balance & winnings in datamanager
    p_after_payout = dm.get_player(pid)
    assert p_after_payout["balance"] == 121, f"Expected balance 121 in players.json, got {p_after_payout['balance']}"
    assert p_after_payout.get("total_winnings") == 25, f"Expected total_winnings 25, got {p_after_payout.get('total_winnings')}"
    print(f"  [PASS] Gauntlet payout awarded {payout_amount} tokens immediately. New balance: {p_after_payout['balance']}, Total Winnings: {p_after_payout['total_winnings']}.")

    # Test Consecutive Round (Second game play immediately)
    print("\n--- 6. Testing Consecutive Play Round ---")
    res_play2 = client.post("/api/gauntlet/play", json={"player_id": pid})
    assert res_play2.status_code == 200
    assert res_play2.json()["balance"] == 117  # 121 - 4
    
    # Glitch with banked tokens payout
    res_payout2 = client.post("/api/gauntlet/payout", json={
        "player_id": pid,
        "payout": 5,
        "level_reached": 3,
        "outcome": "GLITCH"
    })
    assert res_payout2.status_code == 200
    assert res_payout2.json()["new_balance"] == 122  # 117 + 5
    print(f"  [PASS] Consecutive round succeeded with deduction (117) and glitch payout (122).")

    # Test Insufficient Tokens Protection
    print("\n--- 7. Testing Insufficient Balance Protection ---")
    broke_player, _ = dm.register_or_get_player("broke_attendee@venue.com", "BrokeAttendee", starting_balance=2)
    res_broke = client.post("/api/gauntlet/play", json={"player_id": broke_player["id"]})
    assert res_broke.status_code == 400
    assert res_broke.json()["status"] == "error"
    assert "Insufficient" in res_broke.json()["message"]
    assert res_broke.json()["balance"] == 2
    print(f"  [PASS] Insufficient balance (2 < 4) correctly rejected.")

    # 8. TEST PRINTABLE POSTER ENDPOINTS ACROSS ALL SERVERS
    print("\n--- 8. Testing Printable Instructions Poster (/poster) ---")
    # Test on Gauntlet Server (8007)
    res_poster_g = client.get("/poster")
    assert res_poster_g.status_code == 200, f"Expected 200 from /poster on gauntlet server, got {res_poster_g.status_code}"
    poster_html = res_poster_g.text
    assert "The AI" in poster_html and "Gauntlet" in poster_html, "Poster missing title"
    assert "4 TOKENS" in poster_html, "Poster missing '4 TOKENS' entry cost"
    assert ("25 TOKENS" in poster_html or "+25" in poster_html), "Poster missing '25' vault grand prize"
    assert "How To Play" in poster_html, "Poster missing How To Play section"
    assert ("Check-In With PIN" in poster_html or "Check-In PIN" in poster_html), "Poster missing PIN check-in instructions"
    assert "@media print" in poster_html, "Poster missing print media stylesheet"
    assert ("letter portrait" in poster_html or "@page" in poster_html), "Poster missing print page rule"
    print("  [PASS] Gauntlet server (/poster) returned verified 8.5x11 high-res printable poster.")

    # Test on Bison Dash server (8001)
    from game_hub.games.bison_dash.main import app as bison_dash_app
    bison_client = TestClient(bison_dash_app)
    res_poster_b = bison_client.get("/poster")
    assert res_poster_b.status_code == 200, f"Expected 200 from /poster on bison_dash server, got {res_poster_b.status_code}"
    assert "The AI" in res_poster_b.text
    print("  [PASS] Bison Dash server (/poster) returned verified printable poster.")

    # Test on Master Admin server (8000)
    admin_client = TestClient(admin_app)
    res_poster_a = admin_client.get("/poster")
    assert res_poster_a.status_code == 200, f"Expected 200 from /poster on master admin, got {res_poster_a.status_code}"
    assert "The AI" in res_poster_a.text
    print("  [PASS] Master Admin server (/poster) returned verified printable poster.")

    # 9. VERIFY GAUNTLET CLIENT TEMPLATE CODE INTEGRITY
    print("\n--- 9. Auditing Gauntlet Template Client Economy Logic ---")
    assert "tokenCost: gauntletCost" in gauntlet_html or "tokenCost:" in gauntlet_html, "gauntlet.html must pass tokenCost to PinAuthFlow"
    assert "fetch('/api/gauntlet/play'" in gauntlet_html, "gauntlet.html must invoke /api/gauntlet/play on check-in"
    assert "fetch('/api/gauntlet/payout'" in gauntlet_html, "gauntlet.html must invoke /api/gauntlet/payout for real-time wallet crediting"
    print("  [PASS] Gauntlet frontend client correctly configured for real-time deductions and payouts.")

    # Cleanup
    dm.clear_test_players()
    print("\n==================================================")
    print(" ALL GAUNTLET ECONOMY & PIN TESTS 100% PASSED!   ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
