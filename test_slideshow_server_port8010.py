import io
import time
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient

from games.slideshow_server import app as slideshow_app, SLIDESHOW_PORT
from master_admin.main import app as admin_app
from master_admin.process_manager import manager
import master_admin.data_manager as dm

def test_slideshow_server_port8010():
    print("=== STARTING DEDICATED SLIDESHOW SERVER (PORT 8010) TESTS ===")
    assert SLIDESHOW_PORT == 8010, f"Expected port 8010, got {SLIDESHOW_PORT}"
    client = TestClient(slideshow_app)

    # 1. Health check
    print("--- 1. Testing /health endpoint ---")
    res_health = client.get("/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] == "ok"
    assert health_data["service"] == "slideshow_service"
    assert health_data["port"] == 8010
    print(f"[OK] Health check passed on port {health_data['port']}!")

    # 2. Projector UI (/ and /slideshow)
    print("--- 2. Testing Projector Screen HTML endpoints ---")
    for route in ["/", "/slideshow"]:
        res_screen = client.get(route)
        assert res_screen.status_code == 200
        html = res_screen.text
        assert "bison-override-layer" in html
        assert "presentation-override-layer" in html
        assert "F11" in html
        assert "KeyF" in html
        assert "dblclick" in html
        # Zero buttons in presentation layer
        pres_idx = html.find('id="presentation-override-layer"')
        pres_end = html.find('</div>', pres_idx)
        pres_chunk = html[pres_idx:pres_end + 300]
        assert "<button" not in pres_chunk, "DJ Presentation screen must not contain buttons!"
        print(f"[OK] Route {route} served clean projector display successfully!")

    # 3. Presenter Remote UI (/presenter, /remote, /clicker)
    print("--- 3. Testing Presenter Remote Clicker HTML endpoints ---")
    for route in ["/presenter", "/remote", "/clicker"]:
        res_remote = client.get(route)
        assert res_remote.status_code == 200
        text = res_remote.text
        assert "Bison Bash - Stage Slide Remote" in text
        assert "btn-prev" in text and "btn-next" in text
        assert "handleSwipe" in text
        assert "hapticFeedback" in text
        print(f"[OK] Route {route} served mobile presenter remote successfully!")

    # 4. Slide Manifest and Upload on port 8010 backend
    print("--- 4. Testing Slide APIs on Port 8010 Backend ---")
    res_slides = client.get("/api/slides")
    assert res_slides.status_code == 200
    assert "slides" in res_slides.json()

    # Upload slide through port 8010 server
    test_img = Image.new("RGB", (800, 600), color=(100, 200, 50))
    buf = io.BytesIO()
    test_img.save(buf, format="JPEG")
    res_up = client.post(
        "/api/slides/upload",
        files={"file": ("port8010_test.jpg", buf.getvalue(), "image/jpeg")},
        data={"title": "Port 8010 Dedicated Banner"}
    )
    assert res_up.status_code == 200
    up_data = res_up.json()
    assert up_data["status"] == "success"
    slide_id = up_data["slide"]["id"]
    assert up_data["slide"]["width"] == 1920
    assert up_data["slide"]["height"] == 1080
    print(f"[OK] Port 8010 /api/slides/upload created resized slide {slide_id}!")

    # Toggle slide on port 8010
    res_tog = client.post("/api/slides/toggle", json={"slide_id": slide_id, "enabled": False})
    assert res_tog.status_code == 200

    # Clean up uploaded slide
    res_del = client.delete(f"/api/slides/{slide_id}")
    assert res_del.status_code == 200
    print("[OK] Port 8010 slide toggle & delete verified!")

    # 5. Presentation cut-in deck APIs on port 8010
    print("--- 5. Testing Presentation Cut-In Deck APIs ---")
    pres_img = Image.new("RGB", (1280, 720), color=(220, 20, 60))
    p_buf = io.BytesIO()
    pres_img.save(p_buf, format="PNG")
    res_pres_up = client.post(
        "/api/slides/upload",
        files={"file": ("pres_test8010.png", p_buf.getvalue(), "image/png")},
        data={"title": "Speaker Deck Slide 1", "deck": "presentation"}
    )
    assert res_pres_up.status_code == 200
    pres_slide_id = res_pres_up.json()["slide"]["id"]

    res_pres_list = client.get("/api/slides/presentation")
    assert res_pres_list.status_code == 200
    assert any(s["id"] == pres_slide_id for s in res_pres_list.json()["slides"])

    # Start presentation mode on port 8010
    res_pstart = client.post("/api/slideshow/presentation/start", json={"slide_index": 0})
    assert res_pstart.status_code == 200
    assert res_pstart.json()["state"]["mode"] == "presentation"
    assert res_pstart.json()["state"]["presentation"]["active"] is True

    # Step presentation
    res_pstep = client.post("/api/slideshow/presentation/step", json={"delta": 1})
    assert res_pstep.status_code == 200

    # Set index
    res_pidx = client.post("/api/slideshow/presentation/set_index", json={"index": 0})
    assert res_pidx.status_code == 200
    assert res_pidx.json()["state"]["presentation"]["current_index"] == 0

    # Stop presentation
    res_pstop = client.post("/api/slideshow/presentation/stop")
    assert res_pstop.status_code == 200
    assert res_pstop.json()["state"]["mode"] == "slideshow"

    # Cleanup presentation slide
    res_pdel = client.delete(f"/api/slides/presentation/{pres_slide_id}")
    assert res_pdel.status_code == 200
    print("[OK] Presentation cut-in deck lifecycle verified on Port 8010!")

    # 6. Countdown & Restart regular APIs on port 8010
    print("--- 6. Testing Countdown and Restart Regular APIs ---")
    res_cd = client.post("/api/slideshow/bison/start_countdown", json={"minutes": 2, "seconds": 0})
    assert res_cd.status_code == 200
    assert res_cd.json()["state"]["mode"] == "bison_countdown"

    res_restart = client.post("/api/slideshow/restart_regular")
    assert res_restart.status_code == 200
    assert res_restart.json()["state"]["mode"] == "slideshow"
    assert res_restart.json()["state"]["restart_trigger"] > 0
    print("[OK] Countdown & restart_regular APIs verified on Port 8010!")

    # 7. Players manifest leaderboard endpoint on port 8010
    print("--- 7. Testing /api/players/manifest on Port 8010 ---")
    res_mani = client.get("/api/players/manifest")
    assert res_mani.status_code == 200
    assert "players" in res_mani.json()
    print("[OK] Leaderboard manifest endpoint verified on Port 8010!")

    # 8. Process Manager Registration in Master Admin
    print("--- 8. Testing Process Manager Registration in Master Admin ---")
    status = manager.get_status()
    assert "slideshow" in status, "slideshow process must be registered in manager!"
    assert status["slideshow"]["port"] == 8010
    assert manager.processes["slideshow"].module_path == "games.slideshow_server:app"
    print(f"[OK] ProcessManager registered 'slideshow' on port {status['slideshow']['port']} -> games.slideshow_server:app!")

    # 9. Dashboard verification
    print("--- 9. Testing Dashboard Integration for Port 8010 ---")
    admin_client = TestClient(admin_app)
    res_dash = admin_client.get("/")
    assert res_dash.status_code == 200
    d_html = res_dash.text
    assert "http://127.0.0.1:8010/slideshow" in d_html
    assert "http://127.0.0.1:8010/presenter" in d_html
    assert "status-slideshow" in d_html
    assert "8010" in d_html
    print("[OK] Master Admin Dashboard references Port 8010 correctly!")

    print("\n=======================================================")
    print(">>> ALL PORT 8010 FASTAPI DEDICATED TESTS PASSED! <<<")
    print("=======================================================")

if __name__ == "__main__":
    test_slideshow_server_port8010()
