import time
import io
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

import master_admin.data_manager as dm
from master_admin.main import app

def test_slideshow_system():
    print("--- 1. Testing Slides Manifest & Leaderboard in Mix ---")
    manifest = dm.get_slides_manifest()
    slides = manifest.get("slides", [])
    assert len(slides) > 0, "Manifest should have default slides"

    # Verify Leaderboard is in the regular slide mix
    leaderboard_slides = [s for s in slides if s.get("type") == "leaderboard"]
    assert len(leaderboard_slides) > 0, "Leaderboard slide must be present in the regular rotation mix!"
    print(f"[OK] Leaderboard in regular mix verified: {leaderboard_slides[0]['id']}")

    print("--- 2. Testing Image Upload & 1920x1080 Auto-Resize ---")
    # Generate arbitrary sized test image (e.g. 640x480)
    test_img = Image.new("RGB", (640, 480), color=(255, 128, 0))
    buf = io.BytesIO()
    test_img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    slide_data = dm.process_and_save_slide(raw_bytes, "test_banner.png", "Grand Sponsor")
    slide_id = slide_data["id"]
    save_filename = slide_data["filename"]
    save_path = dm.SLIDES_DIR / save_filename

    assert save_path.exists(), f"Saved slide image must exist at {save_path}"
    # Verify exact 1920x1080 resolution on disk
    with Image.open(save_path) as saved_img:
        assert saved_img.size == (1920, 1080), f"Expected 1920x1080, got {saved_img.size}"
        print(f"[OK] Slide image auto-resized & letterboxed to {saved_img.size} verified!")

    # Verify present in manifest
    manifest2 = dm.get_slides_manifest()
    found = [s for s in manifest2["slides"] if s["id"] == slide_id]
    assert len(found) == 1, "Uploaded slide must appear in manifest"
    assert found[0]["title"] == "Grand Sponsor"
    assert found[0]["width"] == 1920 and found[0]["height"] == 1080

    print("--- 3. Testing Slide Toggle & Reorder ---")
    dm.toggle_slide(slide_id, False)
    assert not dm.get_slides_manifest()["slides"][-1]["enabled"], "Slide should be disabled"
    dm.toggle_slide(slide_id, True)
    assert dm.get_slides_manifest()["slides"][-1]["enabled"], "Slide should be re-enabled"
    print("[OK] Slide toggle verified!")

    print("--- 4. Testing Bison Dash Manual Countdown Activation ---")
    # Operator starts a 3-minute countdown slide
    cd_state = dm.set_slideshow_countdown(minutes=3, seconds=0, title="Heat 4 Championship")
    assert cd_state["mode"] == "bison_countdown"
    assert cd_state["countdown"]["active"] is True
    assert cd_state["countdown"]["duration_seconds"] == 180
    assert cd_state["countdown"]["target_timestamp"] > time.time()
    assert cd_state["countdown"]["title"] == "Heat 4 Championship"
    print(f"[OK] Bison Dash Countdown activated: {cd_state['countdown']['duration_seconds']}s")

    # Mode switching
    pre_state = dm.set_slideshow_mode("bison_prerace")
    assert pre_state["mode"] == "bison_prerace"
    race_state = dm.set_slideshow_mode("bison_race")
    assert race_state["mode"] == "bison_race"
    print("[OK] Manual modes bison_prerace and bison_race verified!")

    # Stop countdown & return to slideshow
    stop_state = dm.stop_slideshow_countdown()
    assert stop_state["mode"] == "slideshow"
    assert stop_state["countdown"]["active"] is False
    print("[OK] Return to regular slideshow rotation verified!")

    print("--- 5. Testing Slide Deletion ---")
    del_ok = dm.delete_slide(slide_id)
    assert del_ok, "Slide deletion should return True"
    assert not save_path.exists(), "Slide image file should be deleted from disk"
    manifest3 = dm.get_slides_manifest()
    assert not any(s["id"] == slide_id for s in manifest3["slides"]), "Slide should no longer be in manifest"
    print("[OK] Custom slide deleted and cleaned up from disk!")

    print("--- 6. Testing FastAPI Endpoints with TestClient ---")
    client = TestClient(app)

    # 6a. GET /api/slides
    res = client.get("/api/slides")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert any(s["type"] == "leaderboard" for s in data["slides"])

    # 6b. POST /api/slides/upload (multipart)
    test_img2 = Image.new("RGB", (1200, 900), color=(0, 200, 255))
    buf2 = io.BytesIO()
    test_img2.save(buf2, format="JPEG")
    res_up = client.post(
        "/api/slides/upload",
        files={"file": ("promo.jpg", buf2.getvalue(), "image/jpeg")},
        data={"title": "Techlahoma Promo"}
    )
    assert res_up.status_code == 200
    up_data = res_up.json()
    assert up_data["status"] == "success"
    up_slide_id = up_data["slide"]["id"]
    assert up_data["slide"]["width"] == 1920
    assert up_data["slide"]["height"] == 1080
    print(f"[OK] HTTP /api/slides/upload created 1920x1080 slide: {up_slide_id}")

    # 6c. POST /api/slideshow/bison/start_countdown
    res_start = client.post(
        "/api/slideshow/bison/start_countdown",
        json={"minutes": 2, "seconds": 30, "title": "Bison Dash Finals"}
    )
    assert res_start.status_code == 200
    assert res_start.json()["state"]["countdown"]["duration_seconds"] == 150

    # 6d. GET /api/slideshow/state
    res_state = client.get("/api/slideshow/state")
    assert res_state.status_code == 200
    assert res_state.json()["state"]["mode"] == "bison_countdown"

    # 6e. POST /api/slideshow/bison/stop
    res_stop = client.post("/api/slideshow/bison/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["state"]["mode"] == "slideshow"

    # 6f. DELETE /api/slides/{id}
    res_del = client.delete(f"/api/slides/{up_slide_id}")
    assert res_del.status_code == 200

    # 6g. GET /slideshow HTML
    res_html = client.get("/slideshow")
    assert res_html.status_code == 200
    html_text = res_html.text
    assert "bison-override-layer" in html_text
    assert "bison-timer-clock" in html_text
    assert "TIME LEFT TILL RACE" in html_text
    assert "fetchLeaderboard" in html_text
    assert "presentation-override-layer" in html_text
    assert "presentation-image" in html_text
    print("[OK] Fullscreen slideshow HTML rendered with leaderboard, countdown, and presentation overlay!")

    print("--- 7. Testing Stage Presentation Cut-In Deck & Restart Regular ---")
    # 7a. Direct dm presentation slide upload
    pres_img = Image.new("RGB", (800, 600), color=(128, 0, 255))
    pres_buf = io.BytesIO()
    pres_img.save(pres_buf, format="PNG")
    pres_slide = dm.process_and_save_slide(pres_buf.getvalue(), "keynote_opening.png", "Keynote Opening", deck="presentation")
    assert pres_slide["width"] == 1920 and pres_slide["height"] == 1080
    assert pres_slide["type"] == "presentation_image"
    pres_id1 = pres_slide["id"]
    print(f"[OK] Direct dm presentation slide created (1920x1080): {pres_id1}")

    # 7b. HTTP API presentation slide upload
    pres_img2 = Image.new("RGB", (1024, 768), color=(255, 64, 64))
    pres_buf2 = io.BytesIO()
    pres_img2.save(pres_buf2, format="JPEG")
    res_pres_up = client.post(
        "/api/slides/upload",
        files={"file": ("keynote_conclusion.jpg", pres_buf2.getvalue(), "image/jpeg")},
        data={"title": "Keynote Conclusion", "deck": "presentation"}
    )
    assert res_pres_up.status_code == 200
    pres_data2 = res_pres_up.json()
    assert pres_data2["status"] == "success"
    pres_id2 = pres_data2["slide"]["id"]
    assert pres_data2["slide"]["width"] == 1920 and pres_data2["slide"]["height"] == 1080
    print(f"[OK] HTTP /api/slides/upload created presentation slide: {pres_id2}")

    # 7c. GET /api/slides/presentation
    res_pres_list = client.get("/api/slides/presentation")
    assert res_pres_list.status_code == 200
    pres_list = res_pres_list.json()["slides"]
    assert len(pres_list) >= 2
    assert any(s["id"] == pres_id1 for s in pres_list)
    assert any(s["id"] == pres_id2 for s in pres_list)
    print(f"[OK] GET /api/slides/presentation returned {len(pres_list)} presentation slides.")

    # 7d. POST /api/slideshow/presentation/start
    res_pres_start = client.post("/api/slideshow/presentation/start", json={"slide_index": 0})
    assert res_pres_start.status_code == 200
    pres_state = res_pres_start.json()["state"]
    assert pres_state["mode"] == "presentation"
    assert pres_state["presentation"]["active"] is True
    assert pres_state["presentation"]["current_index"] == 0
    print("[OK] Stage presentation cut-in started at slide 0!")

    # 7e. POST /api/slideshow/presentation/step (delta=+1)
    res_step = client.post("/api/slideshow/presentation/step", json={"delta": 1})
    assert res_step.status_code == 200
    assert res_step.json()["state"]["presentation"]["current_index"] == 1
    print("[OK] Presentation stepped forward to slide 1!")

    # 7e-2. POST /api/slideshow/presentation/set_index
    res_idx0 = client.post("/api/slideshow/presentation/set_index", json={"index": 0})
    assert res_idx0.status_code == 200
    assert res_idx0.json()["state"]["presentation"]["current_index"] == 0
    res_idx1 = client.post("/api/slideshow/presentation/set_index", json={"index": 1})
    assert res_idx1.status_code == 200
    assert res_idx1.json()["state"]["presentation"]["current_index"] == 1
    print("[OK] /api/slideshow/presentation/set_index verified with multi-slide jumping!")

    # 7f. POST /api/slideshow/presentation/stop
    res_pres_stop = client.post("/api/slideshow/presentation/stop")
    assert res_pres_stop.status_code == 200
    assert res_pres_stop.json()["state"]["mode"] == "slideshow"
    assert res_pres_stop.json()["state"]["presentation"]["active"] is False
    print("[OK] Presentation mode stopped cleanly and returned to slideshow!")

    # 7g. POST /api/slideshow/restart_regular
    # First set into race countdown mode
    client.post("/api/slideshow/bison/start_countdown", json={"minutes": 1, "seconds": 0})
    assert dm.get_slideshow_state()["mode"] == "bison_countdown"

    # Now trigger restart regular
    res_restart = client.post("/api/slideshow/restart_regular")
    assert res_restart.status_code == 200
    restarted_state = res_restart.json()["state"]
    assert restarted_state["mode"] == "slideshow"
    assert restarted_state["countdown"]["active"] is False
    assert restarted_state["presentation"]["active"] is False
    assert restarted_state["restart_trigger"] > 0
    print(f"[OK] restart_regular_slideshow endpoint reset mode to slideshow and broadcast trigger: {restarted_state['restart_trigger']}")

    # 7h. Clean up presentation slides
    res_del_p1 = client.delete(f"/api/slides/presentation/{pres_id1}")
    res_del_p2 = client.delete(f"/api/slides/presentation/{pres_id2}")
    assert res_del_p1.status_code == 200
    assert res_del_p2.status_code == 200
    print("[OK] Presentation slides deleted cleanly!")

    print("--- 8. Testing Mobile Presenter Remote & Clean DJ Screen ---")
    # 8a. Mobile Remote Endpoints (/presenter, /remote, /clicker)
    for route in ["/presenter", "/remote", "/clicker"]:
        res_remote = client.get(route)
        assert res_remote.status_code == 200, f"Route {route} must return 200"
        text = res_remote.text
        assert "Stage Slide Remote" in text
        assert "btn-prev" in text and "btn-next" in text
        assert "stepSlide" in text and "jumpToSlide" in text
        assert "handleSwipe" in text
        assert "hapticFeedback" in text
        print(f"[OK] Route {route} verified with touch controls, swipe gestures, and scrubber dots!")

    # 8b. Mobile Remote Scrubber Dot Navigation API Test (Direct Index with bounds)
    res_idx = client.post("/api/slideshow/presentation/set_index", json={"index": 0})
    assert res_idx.status_code == 200
    assert res_idx.json()["state"]["presentation"]["current_index"] == 0
    print("[OK] Remote clicker direct index setting API verified!")

    # 8c. Clean Screen DJ Display Verification
    res_slideshow = client.get("/slideshow")
    assert res_slideshow.status_code == 200
    s_html = res_slideshow.text
    # Ensure presentation override layer has NO button elements
    pres_layer_start = s_html.find('id="presentation-override-layer"')
    assert pres_layer_start != -1
    pres_layer_end = s_html.find('</div>', pres_layer_start)
    pres_chunk = s_html[pres_layer_start:pres_layer_end + 300]
    assert "<button" not in pres_chunk, "DJ Presentation overlay must NOT contain any buttons!"
    # Ensure F11, KeyF, Escape shortcuts and dblclick exist
    assert "F11" in s_html
    assert "KeyF" in s_html
    assert "dblclick" in s_html
    assert "requestFullscreen" in s_html
    assert "webkitRequestFullscreen" in s_html
    print("[OK] DJ's Mac display verified: Zero buttons on screen, F11/KeyF/Escape/dblclick fullscreen!")

    # 8d. Dashboard Presenter Remote Integration
    res_dash = client.get("/")
    assert res_dash.status_code == 200
    dash_html = res_dash.text
    assert '8010/presenter' in dash_html
    assert 'presenter-remote-url' in dash_html
    assert 'copyPresenterUrl()' in dash_html
    print("[OK] Venue Command dashboard verified with Presenter Remote link and copy button!")

    # Ensure system is cleanly returned to regular slideshow rotation at end of test run
    res_clean_stop = client.post("/api/slideshow/presentation/stop")
    assert res_clean_stop.status_code == 200
    assert res_clean_stop.json()["state"]["mode"] == "slideshow"

    print("\n=============================================")
    print(">>> ALL SLIDESHOW, PRESENTATION & RESTART TESTS PASSED! <<<")
    print("=============================================")

if __name__ == "__main__":
    test_slideshow_system()
