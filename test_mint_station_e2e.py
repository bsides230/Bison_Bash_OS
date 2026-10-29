import json
import os
import time
from pathlib import Path
from fastapi.testclient import TestClient

import master_admin.data_manager as dm
from games.token_bank_server import app as bank_app
from master_admin.main import app as admin_app

def test_mint_station_e2e():
    print("--- 1. Testing Test Attendee Setup ---")
    test_email = "mint_tester@example.com"
    test_name = "Mint Test Hero"
    player, _ = dm.register_or_get_player(test_email, test_name, starting_balance=100)
    pin = dm.get_pin_for_player(player["id"])
    assert pin is not None and len(pin) == 4, f"PIN should be 4 digits, got {pin}"
    print(f"Created/retrieved test player: {test_name}, PIN: {pin}, Balance: {player['balance']}")

    # Ensure token ledger files start clean or verified
    ledger_path = Path("data/token_ledger.jsonl")

    # Test with both bank_app (Port 8005) and admin_app (Port 8000)
    for app_name, client in [("TokenBank (8005)", TestClient(bank_app)), ("MasterAdmin (8000)", TestClient(admin_app))]:
        print(f"\n--- Testing API on {app_name} ---")

        # 1. Invalid PIN lookup
        resp_bad = client.post("/api/attendee/lookup", json={"pin": "0000"})
        assert resp_bad.status_code == 404, f"Expected 404 for bad PIN, got {resp_bad.status_code}"
        data_bad = resp_bad.json()
        assert data_bad.get("success") is False
        assert "Invalid PIN" in data_bad.get("error", "")
        print("[PASS] Invalid PIN lookup rejected with 404 & Invalid PIN error")

        # 2. Valid PIN lookup
        resp_good = client.post("/api/attendee/lookup", json={"pin": pin})
        assert resp_good.status_code == 200, f"Expected 200 for good PIN, got {resp_good.status_code}"
        data_good = resp_good.json()
        assert data_good.get("success") is True
        assert data_good.get("display_name") == test_name
        assert data_good.get("email") == test_email
        starting_balance = data_good.get("balance")
        print(f"[PASS] Valid PIN lookup succeeded: Name='{data_good.get('display_name')}', Balance={starting_balance}")

        # 3. Mint tokens: donation_amount = 40, tokens_to_add = 40
        time_before = time.time()
        resp_mint = client.post("/api/mint/tokens", json={
            "pin": pin,
            "donation_amount": 40,
            "tokens_to_add": 40
        })
        assert resp_mint.status_code == 200, f"Expected 200 for mint, got {resp_mint.status_code}: {resp_mint.text}"
        data_mint = resp_mint.json()
        assert data_mint.get("success") is True
        expected_balance = starting_balance + 40
        assert data_mint.get("new_balance") == expected_balance, f"Expected balance {expected_balance}, got {data_mint.get('new_balance')}"
        print(f"[PASS] Mint endpoint succeeded! New balance: {data_mint.get('new_balance')}")

        # 4. Verify pin_last_used was updated
        last_used = dm.pin_last_used.get(pin, 0)
        assert last_used >= time_before, f"pin_last_used was not updated: {last_used} vs {time_before}"
        print(f"[PASS] pin_last_used cooldown timestamp verified: {last_used}")

        # 5. Verify token_ledger.jsonl
        assert ledger_path.exists(), f"Ledger file {ledger_path} should exist"
        with open(ledger_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
        last_entry = json.loads(lines[-1])
        assert last_entry["pin"] == pin
        assert last_entry["donation_amount"] == 40.0
        assert last_entry["tokens_credited"] == 40
        assert last_entry["new_balance"] == expected_balance
        assert "timestamp" in last_entry
        print(f"[PASS] Token ledger verified in data/token_ledger.jsonl: {last_entry}")

    # 6. Verify HTML Template UI structure
    print("\n--- Testing mint.html template structure ---")
    for tpath in ["templates/mint.html", "master_admin/templates/mint.html"]:
        assert os.path.exists(tpath), f"File {tpath} must exist"
        html = open(tpath, "r", encoding="utf-8").read()

        # Step 1 checks
        assert 'id="step-1-pin-pad"' in html
        assert 'type="tel"' in html
        assert 'maxlength="4"' in html
        assert 'pattern="[0-9]*"' in html
        assert 'id="pin-boxes-container"' in html
        assert 'pressPinDigit' in html
        assert 'lookupAttendee' in html

        # Step 2 checks
        assert 'id="step-2-confirm"' in html
        assert 'id="attendee-display-name"' in html
        assert 'id="attendee-email"' in html
        assert 'id="attendee-starting-balance"' in html
        assert 'id="confirm-btn"' in html
        assert 'id="cancel-btn"' in html
        assert '>Confirm</button>' in html
        assert '>Cancel</button>' in html

        # Step 3 checks
        assert 'id="step-3-mint"' in html
        assert 'id="summary-attendee-name"' in html
        assert 'id="summary-starting-balance"' in html
        assert 'id="summary-cumulative-donated"' in html
        assert 'id="summary-resulting-balance"' in html
        # Chips
        for chip_val in [1, 5, 10, 20, 50, 100]:
            assert f"addDonation({chip_val})" in html, f"Missing chip for {chip_val}"
        # Manual entry
        assert 'id="manual-amount-input"' in html
        assert 'id="add-manual-btn"' in html
        # Reset total button
        assert 'id="reset-total-btn"' in html
        assert '>Reset Total</button>' in html
        # Action buttons
        assert 'id="done-btn"' in html
        assert '>Done</button>' in html
        assert 'id="cancel-mint-btn"' in html
        assert '>Cancel</button>' in html

        # Zero localStorage/sessionStorage persistence check
        assert "localStorage" not in html
        assert "sessionStorage" not in html
        print(f"[PASS] All template checks passed for {tpath}")

    print("\n=== ALL TOKEN MINT STATION E2E TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    test_mint_station_e2e()
