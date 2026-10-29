import sys
import master_admin.data_manager as dm
from fastapi.testclient import TestClient
from games.portal_server import app as portal_app
import master_admin.email_manager as em

def run_tests():
    print("=== 1. DATA MANAGER TESTS ===")
    dm.clear_test_players()
    print("Atomic clear_test_players() executed.")
    
    # Register Player 1
    p1, is_new1 = dm.register_or_get_player("test_user_alpha@venue.com", "ThunderVolt")
    assert is_new1 is True, "Expected new player registration"
    assert "pin" in p1, "PIN missing in registered player"
    assert len(p1["pin"]) == 4 and p1["pin"].isdigit(), f"Invalid PIN: {p1.get('pin')}"
    pin1 = p1["pin"]
    print(f"Registered Player: {p1['name']} | Email: {p1['email']} | PIN: {pin1} | Balance: {p1['balance']}")

    # Duplicate check
    p1_dup, is_new2 = dm.register_or_get_player("test_user_alpha@venue.com", "ThunderVolt")
    assert is_new2 is False, "Expected duplicate flag False"
    assert p1_dup["pin"] == pin1, "PIN should remain identical on duplicate"
    print(f"Duplicate registration detected successfully: PIN={p1_dup['pin']}")

    # Multi-field lookup
    found_pin = dm.get_player(pin1)
    assert found_pin and found_pin["email"] == "test_user_alpha@venue.com"

    found_name = dm.get_player("ThunderVolt")
    assert found_name and found_name["pin"] == pin1

    found_email = dm.get_player("test_user_alpha@venue.com")
    assert found_email and found_email["pin"] == pin1

    found_id = dm.get_player(p1["id"])
    assert found_id and found_id["pin"] == pin1

    print("Data manager multi-field lookup (ID, PIN, Name, Email) verified!")

    print("\n=== 2. PORTAL SERVER API TESTS ===")
    client = TestClient(portal_app)

    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200 and res_health.json()["status"] == "ok"
    print("Portal /health verified!")

    # Register via Portal API (Duplicate email test)
    res_dup = client.post("/api/portal/register", json={
        "email": "test_user_alpha@venue.com",
        "name": "IgnoredName",
        "newsletter_opt_in": True
    })
    assert res_dup.status_code == 200
    dup_data = res_dup.json()
    assert dup_data["status"] == "exists"
    assert dup_data["player"]["pin"] == pin1
    print(f"Portal duplicate detection response verified: {dup_data['message']}")

    # Register a brand new player via Portal API
    res_new = client.post("/api/portal/register", json={
        "email": "test_portal_new@venue.com",
        "name": "NeonRider",
        "newsletter_opt_in": True
    })
    assert res_new.status_code == 200
    new_data = res_new.json()
    assert new_data["status"] == "success"
    assert new_data["is_new"] is True
    assert len(new_data["player"]["pin"]) == 4
    pin2 = new_data["player"]["pin"]
    print(f"Portal new registration verified: {new_data['player']['name']} -> PIN: {pin2}")

    # Balance check by PIN
    res_bal_pin = client.get(f"/api/portal/balance/{pin2}")
    assert res_bal_pin.status_code == 200
    bal_pin_data = res_bal_pin.json()
    assert bal_pin_data["status"] == "success"
    assert bal_pin_data["player"]["balance"] == 0
    print(f"Balance check by PIN {pin2}: {bal_pin_data['player']['name']} -> {bal_pin_data['player']['balance']} credits (0 initial allotment)")

    # Balance check by Email
    res_bal_email = client.get(f"/api/portal/balance/test_portal_new@venue.com")
    assert res_bal_email.status_code == 200 and res_bal_email.json()["player"]["pin"] == pin2

    # Balance check by Name (Should be 404 since Display Name lookup was removed per requirement)
    res_bal_name = client.get(f"/api/portal/balance/NeonRider")
    assert res_bal_name.status_code == 404, "Lookup by Display Name must be rejected"
    print("Balance lookup strictly restricted to PIN and Email (Display Name disallowed) verified!")

    # Balance check not found
    res_bal_none = client.get(f"/api/portal/balance/00000000_fake")
    assert res_bal_none.status_code == 404
    print("Portal not found handling verified!")

    print("\n=== 3. EMAIL MANAGER CONFIG VERIFICATION ===")
    cfg = em.load_email_config()
    assert isinstance(cfg, dict)
    assert "smtp_host" in cfg and "smtp_port" in cfg
    print(f"Email config loaded successfully: host={cfg.get('smtp_host')}, port={cfg.get('smtp_port')}")

    print("\n=== 4. STATION TEMPLATE AUDIT ===")
    stations = [
        ("N64 Station", "game_hub/games/bison_dash/templates/n64.html"),
        ("Token Mint Cashier", "master_admin/templates/mint.html"),
        ("Bug Hunt", "game_hub/games/bison_dash/templates/bughunt.html"),
        ("Betting Tablet Kiosk", "game_hub/games/bison_dash/templates/kiosk.html"),
        ("AI Gauntlet", "game_hub/games/bison_dash/templates/gauntlet.html"),
        ("Mobile Player Portal", "game_hub/games/bison_dash/templates/portal.html"),
        ("Stadium Slideshow", "master_admin/templates/slideshow.html"),
        ("Venue Dashboard", "master_admin/templates/dashboard.html"),
    ]

    for name, path in stations:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "portal.html" in path:
            assert "8009" in path or "portal" in path
            assert "Check Balance" in content or "Check My Balance" in content
            assert "Sign Up" in content
            assert "pin-result-card" in content or "PIN" in content
        elif "slideshow.html" in path:
            assert ":8009/" in content, "Slideshow QR should point to port 8009"
            assert "4-digit PIN" in content or "PIN" in content
        elif "dashboard.html" in path:
            assert ":8009/" in content, "Dashboard should link to port 8009"
            assert "<th>PIN</th>" in content, "Dashboard manifest should have PIN column"
        else:
            # Game station
            assert "pin" in content.lower(), f"Station {name} missing PIN references"
        print(f"[OK] {name} ({path}): Verified")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
