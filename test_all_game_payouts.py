import master_admin.data_manager as dm
from fastapi.testclient import TestClient

from games.bughunt_server import app as bughunt_app
from games.n64_server import app as n64_app
from games.gauntlet_server import app as gauntlet_app
from games.plinko_server import app as plinko_app
from games.portal_server import app as portal_app
from master_admin.main import app as admin_app
from game_hub.games.bison_dash.main import app as bd_app
import master_admin.bison_ledger as bison_ledger

def test_all():
    print("=== TESTING ALL GAME PAYOUTS ===")
    p, _ = dm.register_or_get_player("test_payout_master@test.com", "PayoutTester", starting_balance=100)
    pid = p["id"]
    pin = p["pin"]
    print(f"Test Player: {p['name']} ({pid}), PIN: {pin}, Balance: {p['balance']}")

    # 1. Bug Hunt Server (:8003)
    client = TestClient(bughunt_app)
    r = client.post("/api/bughunt/payout", json={"player_id": pid, "bugs": 15, "pity_credit": False})
    assert r.status_code == 200, f"bughunt fail: {r.text}"
    assert r.json()["status"] == "success"
    print("[PASS] bughunt_server /api/bughunt/payout:", r.json())

    # Test by PIN
    r = client.post("/api/bughunt/payout", json={"pin": pin, "bugs": 10})
    assert r.status_code == 200
    print("[PASS] bughunt_server /api/bughunt/payout by PIN:", r.json())

    # 2. N64 Server (:8004)
    client = TestClient(n64_app)
    r = client.post("/api/n64/payout", json={"winner_id": pid, "tokens": 10})
    assert r.status_code == 200, f"n64 fail: {r.text}"
    assert r.json()["status"] == "success"
    print("[PASS] n64_server /api/n64/payout:", r.json())

    # Test by PIN and default tokens
    r = client.post("/api/n64/payout", json={"winner_id": pin, "tokens": 0})
    assert r.status_code == 200, f"n64 pin fail: {r.text}"
    assert r.json()["tokens"] == 10
    print("[PASS] n64_server /api/n64/payout by PIN with default tokens:", r.json())

    # 3. Gauntlet Server (:8007)
    client = TestClient(gauntlet_app)
    r = client.post("/api/gauntlet/payout", json={"player_id": pid, "payout": 25})
    assert r.status_code == 200, f"gauntlet fail: {r.text}"
    assert r.json()["status"] == "success"
    print("[PASS] gauntlet_server /api/gauntlet/payout:", r.json())

    # 4. Plinko Server (:8006)
    client = TestClient(plinko_app)
    r = client.post("/api/plinko/payout", json={"player_id": pid, "payout": 5, "slot_index": 4, "port": 8000})
    assert r.status_code == 200, f"plinko fail: {r.text}"
    assert r.json()["status"] == "success"
    print("[PASS] plinko_server /api/plinko/payout:", r.json())

    # Plinko minimal payload without slot_index/port
    r = client.post("/api/plinko/payout", json={"player_id": pid, "payout": 2})
    assert r.status_code == 200, f"plinko minimal fail: {r.text}"
    print("[PASS] plinko_server minimal payload (no 422):", r.json())

    # 5. Portal Server (:8009)
    client = TestClient(portal_app)
    for ep, payload in [
        ("/api/bughunt/payout", {"player_id": pid, "bugs": 5}),
        ("/api/gauntlet/payout", {"player_id": pid, "payout": 8}),
        ("/api/n64/payout", {"winner_id": pid, "tokens": 10}),
        ("/api/plinko/payout", {"player_id": pid, "payout": 5})
    ]:
        r = client.post(ep, json=payload)
        assert r.status_code == 200, f"portal {ep} fail: {r.text}"
        print(f"[PASS] portal_server {ep}:", r.json()["status"])

    # 6. Master Admin (:8000)
    client = TestClient(admin_app)
    for ep, payload in [
        ("/api/bughunt/payout", {"player_id": pid, "bugs": 5}),
        ("/api/gauntlet/payout", {"player_id": pid, "payout": 8}),
        ("/api/n64/payout", {"winner_id": pid, "tokens": 10}),
        ("/api/plinko/payout", {"player_id": pid, "payout": 5})
    ]:
        r = client.post(ep, json=payload)
        assert r.status_code == 200, f"admin {ep} fail: {r.text}"
        print(f"[PASS] admin_server {ep}:", r.json()["status"])

    # 7. Bison Dash Arena (:8001)
    client = TestClient(bd_app)
    for ep, payload in [
        ("/api/bughunt/payout", {"player_id": pid, "bugs": 5}),
        ("/api/gauntlet/payout", {"player_id": pid, "payout": 8}),
        ("/api/n64/payout", {"winner_id": pid, "tokens": 10}),
        ("/api/plinko/payout", {"player_id": pid, "payout": 5})
    ]:
        r = client.post(ep, json=payload)
        assert r.status_code == 200, f"bison_dash {ep} fail: {r.text}"
        print(f"[PASS] bison_dash_server {ep}:", r.json()["status"])

    # 8. Bison Dash Ledger Race Settlement
    bison_ledger.clear_active_wagers()
    dm.adjust_player_balance(pid, 50)
    bal_before = dm.get_player(pid)["balance"]
    ok, msg, w = bison_ledger.place_wager(pid, 2, 10, "Cyber Steer")
    assert ok, f"place_wager failed: {msg}"
    assert dm.get_player(pid)["balance"] == bal_before - 10
    res = bison_ledger.settle_race(2, multiplier=2.0)
    assert res["total_paid_out"] == 20
    assert dm.get_player(pid)["balance"] == bal_before + 10 # -10 + 20 = +10
    print("[PASS] bison_ledger.settle_race credited exact single payout and net winnings cleanly.")

    dm.clear_test_players()
    print("\n*** ALL GAME PAYOUTS TESTED AND VERIFIED 100% CLEAN! ***")

if __name__ == "__main__":
    test_all()
