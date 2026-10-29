import json
from pathlib import Path
from fastapi.testclient import TestClient

import master_admin.data_manager as dm
import master_admin.email_manager as em
from master_admin.main import app as admin_app
from games.portal_server import app as portal_app

def test_manifest_modal_overlay_css():
    """Verify manifest modal uses fixed high-z-index overlay covering viewport."""
    dashboard_html = Path("master_admin/templates/dashboard.html").read_text(encoding="utf-8")
    
    assert "#manifest-modal" in dashboard_html
    assert "position: fixed !important;" in dashboard_html
    assert "z-index: 999999 !important;" in dashboard_html
    assert "inset: 0 !important;" in dashboard_html or "top: 0 !important;" in dashboard_html
    assert "closeManifestModal()" in dashboard_html
    
    admin_js = Path("master_admin/static/js/admin.js").read_text(encoding="utf-8")
    assert "function openManifestModal()" in admin_js
    assert "document.body.style.overflow = 'hidden'" in admin_js
    assert "function closeManifestModal()" in admin_js
    assert "document.body.style.overflow = ''" in admin_js
    print("[PASS] Manifest modal overlay CSS and JS verified.")

def test_player_preservation_and_safe_clear():
    """Verify real players are strictly protected and never deleted randomly during test cleans."""
    # 1. Register a real attendee account
    real_email = "sarah.connor.real@gmail.com"
    real_name = "Sarah Connor"
    real_player, is_new = dm.register_or_get_player(real_email, real_name, starting_balance=250)
    real_id = real_player["id"]
    real_pin = real_player["pin"]
    
    # 2. Register synthetic test accounts
    test_player1, _ = dm.register_or_get_player("attendee_999@venue.com", "Attendee_999", starting_balance=100)
    test_player2, _ = dm.register_or_get_player("tester_bob@test.com", "GauntletChamp", starting_balance=100)
    
    # Verify all 3 exist
    assert dm.get_player(real_id) is not None
    assert dm.get_player(test_player1["id"]) is not None
    assert dm.get_player(test_player2["id"]) is not None
    
    # 3. Call clear_test_players() (or default clear_all_players(force=False))
    dm.clear_test_players()
    
    # 4. Verify test players are purged, BUT real player survives!
    assert dm.get_player(test_player1["id"]) is None, "Test player 1 should have been purged!"
    assert dm.get_player(test_player2["id"]) is None, "Test player 2 should have been purged!"
    
    survived = dm.get_player(real_id)
    assert survived is not None, "REAL PLAYER WAS DELETED! Real players must be preserved!"
    assert survived["email"] == real_email
    assert survived["name"] == real_name
    assert survived["balance"] == 250
    assert survived["pin"] == real_pin
    
    # 5. Verify individual file also exists
    pfile = dm.get_player_file(real_id)
    assert pfile.exists(), "Individual player file for real attendee must exist!"
    
    # 6. Verify backup directory was created
    backup_dir = dm.DATA_DIR / "players_safe_backup"
    assert backup_dir.exists()
    assert len(list(backup_dir.glob("players_pre_clear_*.json"))) > 0
    
    # Clean up test-created Sarah Connor player without clearing other accounts
    test_real_file = dm.get_player_file(real_id)
    test_real_file.unlink(missing_ok=True)
    curr_data = dm.read_data(dm.PLAYERS_FILE)
    if real_id in curr_data.get("players", {}):
        del curr_data["players"][real_id]
        dm.write_data(dm.PLAYERS_FILE, curr_data, backup=False)
    print("[PASS] Player preservation and safe clear verified.")

def test_email_template_customization_and_endpoints():
    """Verify email template is editable via API and formats dynamic tokens properly."""
    client = TestClient(admin_app)
    
    # 1. GET /api/email/config
    res = client.get("/api/email/config")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    cfg = data["config"]
    assert "subject_template" in cfg
    assert "body_template" in cfg
    
    # 2. POST /api/email/config with updated templates
    custom_subject = "Exclusive Pass for {name}! PIN: {pin}"
    custom_body = "Hello {name}!\nYour code is {pin} with {balance} tokens.\nHave fun!"
    
    post_res = client.post("/api/email/config", json={
        "subject_template": custom_subject,
        "body_template": custom_body
    })
    assert post_res.status_code == 200
    
    # 3. Verify changes persisted
    reloaded_cfg = em.load_email_config()
    assert reloaded_cfg["subject_template"] == custom_subject
    assert reloaded_cfg["body_template"] == custom_body
    
    # 4. Test format resolution
    formatted_subj = custom_subject.format(name="Alex", pin="1234", balance=100)
    assert formatted_subj == "Exclusive Pass for Alex! PIN: 1234"
    formatted_body = custom_body.format(name="Alex", pin="1234", balance=100)
    assert "Alex" in formatted_body and "1234" in formatted_body and "100" in formatted_body
    
    # 5. Restore default template
    em.save_email_config(em.DEFAULT_CONFIG)
    print("[PASS] Email template customization and API endpoints verified.")

def test_newsletter_removed_from_signup_and_portal():
    """Verify newsletter checkbox and text are completely removed from all attendee registration views."""
    portal_html = Path("game_hub/games/bison_dash/templates/portal.html").read_text(encoding="utf-8")
    assert "newsletter" not in portal_html.lower()
    assert "signup-optin" not in portal_html
    assert "Subscribe to Techlahoma community newsletter" not in portal_html
    
    signup_html = Path("game_hub/games/bison_dash/templates/signup.html").read_text(encoding="utf-8")
    assert "newsletter-opt-in" not in signup_html
    assert "Stay connected with <strong>Techlahoma</strong> newsletters" not in signup_html
    
    # Test registration via portal TestClient
    client = TestClient(portal_app)
    res = client.post("/api/portal/register", json={
        "name": "Signee Test",
        "email": "signee_test_user@example.com"
    })
    assert res.status_code == 200
    pdata = res.json()
    assert pdata["status"] == "success"
    assert pdata["player"]["name"] == "Signee Test"
    
    # Cleanup test player
    dm.clear_test_players()
    print("[PASS] Newsletter removal from portal.html and signup.html verified.")

if __name__ == "__main__":
    test_manifest_modal_overlay_css()
    test_player_preservation_and_safe_clear()
    test_email_template_customization_and_endpoints()
    test_newsletter_removed_from_signup_and_portal()
    print("\nALL SESSION FEATURE TESTS PASSED 100%!")
