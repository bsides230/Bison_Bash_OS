import sys
import os
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure root is in python path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import master_admin.data_manager as dm

def run_tests():
    print("=== STARTING FULL ECONOMY & PAYOUT RULES E2E VERIFICATION ===")

    # 1. Clean slate setup
    dm.clear_test_players()
    dm.save_economy_config(dm.DEFAULT_ECONOMY_CONFIG)
    initial_cfg = dm.get_economy_config()
    assert initial_cfg["initial_allotment"] in (50, 100), f"Expected 50 or 100, got {initial_cfg['initial_allotment']}"
    print("[PASS] Default economy configuration verified.")

    # 2. Test Custom Economy Config Save & Load
    custom_cfg = {
        "initial_allotment": 250,
        "costs": {
            "n64": 15,
            "bughunt": 5,
            "gauntlet": 20,
            "bison_dash_min_bet": 12
        },
        "payouts": {
            "n64_winner": 35,
            "bughunt_bugs_per_token": 4,
            "bughunt_pity_tokens": 2,
            "gauntlet": {
                "stage1": 3,
                "stage2": 6,
                "stage3": 10,
                "stage4": 15,
                "vault_jackpot": 50,
                "vault_runner_up": 20
            },
            "bison_dash_multiplier": 2.5
        }
    }
    dm.save_economy_config(custom_cfg)
    loaded_cfg = dm.get_economy_config()
    assert loaded_cfg["initial_allotment"] == 250
    assert "plinko" not in loaded_cfg["costs"]
    assert loaded_cfg["costs"]["n64"] == 15
    assert loaded_cfg["payouts"]["bison_dash_multiplier"] == 2.5
    print("[PASS] Custom economy configuration saved and persisted with FileLock.")

    # 3. Test Dynamic Allotment upon Player Registration
    player, is_new = dm.register_or_get_player("test_economy@okc.org", "EchoPlayer")
    assert is_new is True
    assert player["balance"] == 250, f"Expected 250 starting credits, got {player['balance']}"
    assert len(player["pin"]) == 4
    pid = player["id"]
    print(f"[PASS] Player registered with dynamic allotment: {player['name']} ({pid}), PIN: {player['pin']}, Balance: {player['balance']}")

    # 4. Test dm.deduct_game_cost
    res_n64 = dm.deduct_game_cost(pid, "n64")
    assert res_n64["allowed"] is True
    assert res_n64["cost"] == 15
    assert res_n64["balance"] == 235

    res_bughunt = dm.deduct_game_cost(pid, "bughunt")
    assert res_bughunt["allowed"] is True
    assert res_bughunt["cost"] == 5
    assert res_bughunt["balance"] == 230

    res_gauntlet = dm.deduct_game_cost(pid, "gauntlet")
    assert res_gauntlet["allowed"] is True
    assert res_gauntlet["cost"] == 20
    assert res_gauntlet["balance"] == 210
    print(f"[PASS] All game cost deductions succeeded. Remaining balance: {res_gauntlet['balance']}")

    # Test insufficient balance protection
    broke_player, _ = dm.register_or_get_player("broke@okc.org", "BrokePlayer", starting_balance=5)
    broke_res = dm.deduct_game_cost(broke_player["id"], "gauntlet")  # Cost is 20, balance is 5
    assert broke_res["allowed"] is False
    assert broke_res["balance"] == 5
    print("[PASS] Insufficient balance protection confirmed.")

    # 5. Test Master Admin API Endpoints
    from master_admin.main import app as admin_app
    admin_client = TestClient(admin_app)

    res = admin_client.get("/api/economy/config")
    assert res.status_code == 200
    assert res.json()["config"]["initial_allotment"] == 250

    # 6. Test Portal Server API
    from games.portal_server import app as portal_app
    portal_client = TestClient(portal_app)

    res = portal_client.get("/api/portal/config")
    assert res.status_code == 200
    assert res.json()["initial_allotment"] == 250
    print("[PASS] Portal server config verified (+250 dynamic allotment).")

    # 7. Test N64 Server API
    from games.n64_server import app as n64_app
    n64_client = TestClient(n64_app)

    res = n64_client.get("/api/n64/config")
    assert res.status_code == 200
    assert res.json()["cost"] == 15
    assert res.json()["winner_payout"] == 35

    def clear_rl():
        dm.pin_last_used.clear()
        if dm.RATE_LIMIT_FILE.exists():
            try:
                dm.RATE_LIMIT_FILE.unlink()
            except Exception:
                pass

    # Register player 2 for match
    clear_rl()
    p2, _ = dm.register_or_get_player("test_p2@test.com", "PlayerTwo")
    res_entry = n64_client.post("/api/n64/entry", json={"p1_id": pid, "p2_id": p2["id"]})
    assert res_entry.status_code == 200
    assert res_entry.json()["p1_balance"] == 195  # 210 - 15
    assert res_entry.json()["p2_balance"] == 235  # 250 - 15

    # Test winner payout with economy winner_payout (35)
    clear_rl()
    res_payout = n64_client.post("/api/n64/payout", json={"winner_id": pid, "tokens": 0})
    assert res_payout.status_code == 200
    assert res_payout.json()["tokens"] == 35
    assert res_payout.json()["new_balance"] == 230  # 195 + 35
    print("[PASS] N64 tournament entry fees and dynamic winner payout (35) verified.")

    # 8. Test Bug Hunt Server API
    from games.bughunt_server import app as bughunt_app
    bughunt_client = TestClient(bughunt_app)

    res = bughunt_client.get("/api/bughunt/config")
    assert res.status_code == 200
    assert res.json()["cost"] == 5
    assert res.json()["bugs_per_token"] == 4
    assert res.json()["pity_tokens"] == 2

    # Play session cost deduction
    clear_rl()
    play_res = bughunt_client.post("/api/bughunt/play", json={"player_id": pid})
    assert play_res.status_code == 200
    assert play_res.json()["balance"] == 225  # 230 - 5

    # Payout: 14 bugs with 4:1 conversion = 3 tokens
    clear_rl()
    res_pay = bughunt_client.post("/api/games/bughunt/payout", json={"player_id": pid, "bugs": 14, "pity_credit": False})
    assert res_pay.status_code == 200
    assert res_pay.json()["tokens"] == 3
    assert res_pay.json()["new_balance"] == 228

    # Payout with toddler pity credit: 2 bugs (normally 0 tokens) -> gives 2 pity tokens
    clear_rl()
    res_pity = bughunt_client.post("/api/games/bughunt/payout", json={"player_id": pid, "bugs": 2, "pity_credit": True})
    assert res_pity.status_code == 200
    assert res_pity.json()["tokens"] == 2
    assert res_pity.json()["new_balance"] == 230
    print("[PASS] Bug Hunt config, play deduction, and dynamic 4:1 conversion & pity credits verified.")

    # 9. Test Gauntlet Server API
    from games.gauntlet_server import app as gauntlet_app
    gauntlet_client = TestClient(gauntlet_app)

    res = gauntlet_client.get("/api/gauntlet/config")
    assert res.status_code == 200
    assert res.json()["cost"] == 20
    assert res.json()["payouts"]["vault_jackpot"] == 50

    # Gauntlet play cost deduction
    clear_rl()
    play_res = gauntlet_client.post("/api/gauntlet/play", json={"player_id": pid})
    assert play_res.status_code == 200
    assert play_res.json()["balance"] == 210  # 230 - 20

    # Gauntlet payout
    clear_rl()
    res_pay = gauntlet_client.post("/api/gauntlet/payout", json={
        "player_id": pid,
        "payout": 50,
        "level_reached": 5,
        "outcome": "JACKPOT"
    })
    assert res_pay.status_code == 200
    assert res_pay.json()["new_balance"] == 260  # 210 + 50
    print("[PASS] AI Gauntlet config, play deduction, and dynamic jackpot payout verified.")

    # 10. Test Bison Dash Server API
    from game_hub.games.bison_dash.main import app as bison_app
    bison_client = TestClient(bison_app)

    res = bison_client.get("/api/bisondash/config")
    assert res.status_code == 200
    assert res.json()["min_bet"] == 12
    assert res.json()["multiplier"] == 2.5
    print("[PASS] Bison Dash min bet (12) and multiplier (2.5x) config verified.")

    # 11. Test Economy Reset API
    res = admin_client.post("/api/economy/reset")
    assert res.status_code == 200
    assert res.json()["config"]["initial_allotment"] in (50, 100)
    assert res.json()["config"]["payouts"]["bison_dash_multiplier"] == 2.0
    print("[PASS] Factory reset API restored default economy successfully.")

    # Clean up test accounts
    dm.clear_test_players()
    print("\n=======================================================")
    print(" ALL ECONOMY & PAYOUT RULES VERIFIED 100% SUCCESSFULLY ")
    print("=======================================================")

if __name__ == "__main__":
    run_tests()
