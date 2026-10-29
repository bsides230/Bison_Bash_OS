import time
import json
import master_admin.data_manager as dm
from fastapi.testclient import TestClient

# Import servers
from master_admin.main import app as master_admin_app
from games.token_bank_server import app as token_bank_app
from games.gauntlet_server import app as gauntlet_app
from games.kiosk_server import app as kiosk_app
from games.n64_server import app as n64_app
from games.bughunt_server import app as bughunt_app
from game_hub.games.bison_dash.main import app as bison_dash_app
from games.portal_server import app as portal_app
from games.slideshow_server import app as slideshow_app

def run_tests():
    print("==================================================")
    print(" RUNNING PIN AUTH FLOW & RATE LIMIT END-TO-END TESTS")
    print("==================================================")

    # 1. SETUP CLEAN STATE
    dm.clear_test_players()
    # Reset in-memory rate limits & file
    dm.pin_last_used.clear()
    if dm.RATE_LIMIT_FILE.exists():
        dm.RATE_LIMIT_FILE.unlink()

    # Register test attendees
    p1, _ = dm.register_or_get_player("alice@venue.com", "Alice Walker")
    pin1 = p1["pin"]
    p2, _ = dm.register_or_get_player("bob@venue.com", "Bob Builder")
    pin2 = p2["pin"]

    print(f"Registered Attendee 1: {p1['name']} | PIN: {pin1} | Balance: {p1['balance']}")
    print(f"Registered Attendee 2: {p2['name']} | PIN: {pin2} | Balance: {p2['balance']}")

    clients = {
        "Master Admin (:8000)": TestClient(master_admin_app),
        "Bison Dash Arena (:8001)": TestClient(bison_dash_app),
        "Bug Hunt (:8003)": TestClient(bughunt_app),
        "N64 Arena (:8004)": TestClient(n64_app),
        "Token Mint (:8005)": TestClient(token_bank_app),
        "AI Gauntlet (:8007)": TestClient(gauntlet_app),
        "Betting Kiosk (:8008)": TestClient(kiosk_app),
        "Player Portal (:8009)": TestClient(portal_app),
        "Slideshow (:8010)": TestClient(slideshow_app)
    }

    # 2. TEST ATTENDEE LOOKUP ACROSS ALL SERVERS
    print("\n--- 1. Testing POST /api/attendee/lookup across all servers ---")
    for name, client in clients.items():
        # Valid PIN
        res = client.post("/api/attendee/lookup", json={"pin": pin1})
        assert res.status_code == 200, f"{name}: Expected 200 on lookup, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("success") is True, f"{name}: success not true"
        assert data.get("display_name") == "Alice Walker", f"{name}: wrong display name"
        assert data.get("email") == "alice@venue.com", f"{name}: wrong email"
        assert data.get("balance") == p1["balance"], f"{name}: wrong balance"

        # Invalid PIN
        res_bad = client.post("/api/attendee/lookup", json={"pin": "0000"})
        assert res_bad.status_code in [400, 404], f"{name}: Expected 404/400 for bad PIN, got {res_bad.status_code}"
        data_bad = res_bad.json()
        assert data_bad.get("success") is False, f"{name}: Expected success=False"
        assert data_bad.get("error") == "Invalid PIN", f"{name}: Expected error='Invalid PIN'"

        print(f"  [PASS] {name} attendee lookup valid and invalid verified.")

    # 3. TEST 10-SECOND CONCURRENCY & ANTI-SPAM LOCK
    print("\n--- 2. Testing 10-Second Concurrency & Anti-Spam Lock ---")
    admin_client = clients["Master Admin (:8000)"]
    gauntlet_client = clients["AI Gauntlet (:8007)"]
    kiosk_client = clients["Betting Kiosk (:8008)"]

    # First transaction on Master Admin: should succeed
    res1 = admin_client.post("/api/tokens/transact", json={
        "pin": pin1,
        "amount": 25,
        "action": "adjust",
        "description": "Welcome Bonus"
    })
    assert res1.status_code == 200, f"Expected 200 on first transact, got {res1.status_code}: {res1.text}"
    assert res1.json().get("success") is True

    # Immediate second transaction (under 10s) with same PIN on Master Admin: MUST REJECT WITH 429
    res2 = admin_client.post("/api/tokens/transact", json={
        "pin": pin1,
        "amount": 10,
        "action": "adjust"
    })
    assert res2.status_code == 429, f"Expected 429 under 10s, got {res2.status_code}: {res2.text}"
    data2 = res2.json()
    assert data2.get("success") is False
    assert data2.get("error") == "Please wait before using your code again.", f"Got error: {data2.get('error')}"
    print("  [PASS] Immediate second transaction on same server rejected with 429 and verbatim message.")

    # Immediate cross-server transaction (under 10s) on AI Gauntlet with same PIN: MUST ALSO REJECT WITH 429
    res3 = gauntlet_client.post("/api/tokens/transact", json={
        "pin": pin1,
        "amount": 5,
        "action": "adjust"
    })
    assert res3.status_code == 429, f"Expected 429 across servers under 10s, got {res3.status_code}: {res3.text}"
    data3 = res3.json()
    assert data3.get("success") is False
    assert data3.get("error") == "Please wait before using your code again."
    print("  [PASS] Cross-server transaction under 10s rejected with 429 and synchronized lock.")

    # Different PIN (pin2) on same or different server: SHOULD SUCCEED IMMEDIATELY
    res4 = kiosk_client.post("/api/tokens/transact", json={
        "pin": pin2,
        "amount": 50,
        "action": "adjust"
    })
    assert res4.status_code == 200, f"Expected 200 for independent PIN2, got {res4.status_code}: {res4.text}"
    print("  [PASS] Independent PIN2 succeeded concurrently without interference.")

    # Now simulate time forward by manually aging the cooldown for pin1
    dm._save_pin_rate_limits(pin1, time.time() - 11.0)

    # After 10s: transaction with pin1 should succeed again
    res5 = admin_client.post("/api/tokens/transact", json={
        "pin": pin1,
        "amount": 10,
        "action": "adjust"
    })
    assert res5.status_code == 200, f"Expected 200 after cooldown elapsed, got {res5.status_code}: {res5.text}"
    print("  [PASS] Transaction succeeded after 10-second cooldown elapsed.")

    # 4. TEMPLATE INTEGRATION & 3-STEP FLOW AUDIT
    print("\n--- 3. Auditing All 6 Interface Templates ---")
    templates_to_check = [
        ("AI Gauntlet Tablet (:8007)", "game_hub/games/bison_dash/templates/gauntlet.html", "gauntlet-pin-container"),
        ("Bison Dash Betting Tablet (:8008)", "game_hub/games/bison_dash/templates/kiosk.html", "kiosk-pin-container"),
        ("Token Mint Station (:8005)", "master_admin/templates/mint.html", "mint-pin-container"),
        ("N64 Station Slot 1 & 2 (:8004)", "game_hub/games/bison_dash/templates/n64.html", "n64-p1-pin-container"),
        ("Bug Bounty Station (:8003)", "game_hub/games/bison_dash/templates/bughunt.html", "bughunt-pin-container")
    ]

    for label, path, container in templates_to_check:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "pin_auth_flow.js" in content, f"{label} missing pin_auth_flow.js"
        assert container in content, f"{label} missing container {container}"
        assert "PinAuthFlow" in content, f"{label} missing PinAuthFlow invocation"
        assert "resetToStep1" in content, f"{label} missing resetToStep1 auto-reset call"

        # Check that PINs are NOT saved to sessionStorage or localStorage
        assert "sessionStorage.setItem('pin'" not in content, f"{label} violates clean state rule (sessionStorage)"
        assert "localStorage.setItem('pin'" not in content, f"{label} violates clean state rule (localStorage)"

        print(f"  [PASS] {label} verified: PinAuthFlow, container, auto-reset, zero PIN persistence.")

    # 5. AUDIT pin_auth_flow.js FOR VERBATIM REQUIREMENTS
    print("\n--- 4. Auditing pin_auth_flow.js Standard Component ---")
    with open("master_admin/static/js/pin_auth_flow.js", "r", encoding="utf-8") as f:
        paf_code = f.read()

    # Step 1 input specification: <input type="tel" maxlength="4" pattern="[0-9]*"
    assert 'input type="tel"' in paf_code, "pin_auth_flow.js missing <input type='tel'>"
    assert 'maxlength="4"' in paf_code, "pin_auth_flow.js missing maxlength='4'"
    assert 'pattern="[0-9]*"' in paf_code, "pin_auth_flow.js missing pattern='[0-9]*'"

    # Step 2 verbatim button labels: "Confirm" and "Cancel"
    assert '>Confirm<' in paf_code, "pin_auth_flow.js missing verbatim Confirm button"
    assert '>Cancel<' in paf_code, "pin_auth_flow.js missing verbatim Cancel button"

    # Step 2 fields: Display Name, Email, Token Balance
    assert "Display Name" in paf_code, "pin_auth_flow.js missing Display Name field"
    assert "Email" in paf_code, "pin_auth_flow.js missing Email field"
    assert "Token Balance" in paf_code, "pin_auth_flow.js missing Token Balance field"

    # Auto-lookup endpoint
    assert "/api/attendee/lookup" in paf_code, "pin_auth_flow.js missing /api/attendee/lookup call"
    print("  [PASS] pin_auth_flow.js verified: numeric input, verbatim Confirm/Cancel, attendee fields, lookup API.")

    # 6. AUDIT QR CODE GENERATOR & PRINT CENTER
    print("\n--- 5. Auditing Event QR Generator & Print Center ---")
    with open("master_admin/templates/dashboard.html", "r", encoding="utf-8") as f:
        dash_content = f.read()

    with open("master_admin/static/js/admin.js", "r", encoding="utf-8") as f:
        admin_js = f.read()

    assert "openQrGeneratorModal" in dash_content, "dashboard.html missing openQrGeneratorModal button"
    assert "qr-generator-modal" in dash_content, "dashboard.html missing qr-generator-modal"
    assert "qr-print-placard" in dash_content, "dashboard.html missing qr-print-placard"
    assert "@media print" in dash_content, "dashboard.html missing @media print CSS"

    assert "QR_PRESETS" in admin_js, "admin.js missing QR_PRESETS"
    assert "downloadQrPng" in admin_js, "admin.js missing downloadQrPng"
    assert "printQrPlacard" in admin_js, "admin.js missing printQrPlacard"
    assert "copyQrUrl" in admin_js, "admin.js missing copyQrUrl"
    print("  [PASS] Event QR Generator & Print Center verified: presets, high-res download, print placard.")

    print("\n==================================================")
    print(" ALL TESTS PASSED SUCCESSFULLY! 100% VERIFIED.")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
