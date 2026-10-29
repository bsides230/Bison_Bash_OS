import sys
import time
import urllib.request
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

import master_admin.data_manager as dm

FUNNEL_BASE = "https://bsidesbook3.stern-lenok.ts.net"

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "TailscaleTester/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def fetch_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "TailscaleTester/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.status, resp.read()

def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "TailscaleTester/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return resp.status, resp.read().decode("utf-8")

def main():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    is_running = (s.connect_ex(('127.0.0.1', 8010)) == 0)
    s.close()

    if not is_running:
        print("[*] Starting slideshow_server on port 8010...")
        import uvicorn, threading
        from games.slideshow_server import app
        t = threading.Thread(target=uvicorn.run, args=(app,), kwargs={'host': '127.0.0.1', 'port': 8010, 'log_level': 'warning'}, daemon=True)
        t.start()
        time.sleep(2)

    print("=== TESTING TAILSCALE FUNNEL SLIDESHOW & CUT-INS ===")
    print(f"Target: {FUNNEL_BASE}/slideshow")

    # 1. Verify Slideshow HTML loads over Tailscale Funnel
    status, html = fetch_text(f"{FUNNEL_BASE}/slideshow")
    assert status == 200, f"Expected 200, got {status}"
    assert "Bison Bash - Stadium Projector Slideshow" in html
    assert 'id="slideDeck"' in html
    assert 'id="presentation-override-layer"' in html
    assert 'id="bison-override-layer"' in html
    print("[PASS] 1. Slideshow HTML loads cleanly over Tailscale Funnel!")

    # 2. Verify Slide manifest and images load over Tailscale Funnel
    status, slides_data = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slides")
    assert status == 200
    assert slides_data.get("status") == "success"
    slides = slides_data.get("slides", [])
    assert len(slides) > 0, "Slides list should not be empty"
    print(f"[PASS] 2. Manifest loads over Tailscale Funnel with {len(slides)} regular slides!")

    # Verify custom slide image accessible
    first_image_slide = next((s for s in slides if s.get("type") == "custom_image"), None)
    if first_image_slide:
        img_url = first_image_slide.get("url")
        status, _ = fetch_bytes(f"{FUNNEL_BASE}/slideshow{img_url}")
        assert status == 200
        print(f"[PASS] Custom slide image accessible over Funnel: {img_url}")

    # 3. Test State API over Funnel
    status, state_resp = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slideshow/state")
    assert status == 200
    assert state_resp.get("status") == "success"
    print("[PASS] 3. State API accessible over Tailscale Funnel!")

    # 4. Test Stage Presentation Cut-In over Tailscale Funnel
    print("\n--- Testing Stage Presentation Cut-In ---")
    dm.start_presentation_mode(slide_index=0)
    time.sleep(0.5)

    status, state_resp = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slideshow/state")
    state = state_resp.get("state", {})
    assert state.get("mode") == "presentation"
    assert state.get("presentation", {}).get("active") is True
    assert state.get("presentation", {}).get("current_index") == 0
    print("[PASS] 4a. Presentation mode activated (slide 0) and verified via Funnel state!")

    # Verify presentation slides API
    status, pres_data = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slides/presentation")
    assert status == 200
    pres_slides = pres_data.get("slides", [])
    assert len(pres_slides) > 0, "Presentation slides should exist"
    print(f"[PASS] 4b. Presentation deck returned {len(pres_slides)} slides over Funnel!")

    # Verify presentation slide image loads over Funnel
    pres_img_url = pres_slides[0].get("url")
    status, _ = fetch_bytes(f"{FUNNEL_BASE}/slideshow{pres_img_url}")
    assert status == 200
    print(f"[PASS] 4c. Presentation slide image loaded over Funnel: {pres_img_url}")

    # Presenter steps forward
    dm.step_presentation_slide(delta=1)
    time.sleep(0.5)
    status, state_resp = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slideshow/state")
    state = state_resp.get("state", {})
    assert state.get("presentation", {}).get("current_index") == 1
    print("[PASS] 4d. Stepped presentation slide to index 1 and verified over Funnel!")

    # Stop presentation
    dm.stop_presentation_mode()
    time.sleep(0.5)
    status, state_resp = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slideshow/state")
    state = state_resp.get("state", {})
    assert state.get("mode") == "slideshow"
    assert state.get("presentation", {}).get("active") is False
    print("[PASS] 4e. Presentation cut-in stopped cleanly, returned to regular slideshow!")

    # 5. Test Race Countdown Cut-In over Tailscale Funnel
    print("\n--- Testing Race Countdown Cut-In ---")
    dm.set_slideshow_countdown(minutes=5, seconds=0, title="Championship Final")
    time.sleep(0.5)

    status, state_resp = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slideshow/state")
    state = state_resp.get("state", {})
    assert state.get("mode") == "bison_countdown"
    assert state.get("countdown", {}).get("active") is True
    assert state.get("countdown", {}).get("title") == "Championship Final"
    print("[PASS] 5a. Countdown cut-in activated (5:00 Championship Final) over Funnel!")

    # Verify cycling bison display asset loads over Funnel
    for slot in [1, 2, 3, 4, 5, 6]:
        bison_asset_url = f"/slideshow/static/display/512/bison_{slot}.png"
        status, _ = fetch_bytes(f"{FUNNEL_BASE}{bison_asset_url}")
        assert status == 200, f"Expected 200 for {bison_asset_url}, got {status}"
    print("[PASS] 5b. All 6 cycling bison showcase images accessible over Funnel!")

    # 6. Test Live Race Track Sprint Cut-In & Projector over Tailscale Funnel
    print("\n--- Testing Live Race Track Sprint Cut-In ---")
    dm.set_slideshow_mode("bison_race")
    time.sleep(0.5)

    status, state_resp = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slideshow/state")
    state = state_resp.get("state", {})
    assert state.get("mode") == "bison_race"
    print("[PASS] 6a. Switched mode to bison_race verified over Funnel!")

    # Verify projector HTML is served through /slideshow/projector over Funnel
    status, proj_html = fetch_text(f"{FUNNEL_BASE}/slideshow/projector")
    assert status == 200
    assert "Bison Dash" in proj_html
    assert 'id="canvas-wrapper"' in proj_html or 'canvas' in proj_html
    print("[PASS] 6b. Projector display iframe loads cleanly via /slideshow/projector over Funnel!")

    # Verify current race API over Funnel
    status, race_data = fetch_json(f"{FUNNEL_BASE}/slideshow/api/current_race")
    assert status == 200
    print("[PASS] 6c. /slideshow/api/current_race returned telemetry data over Funnel!")

    # Stop race and resume regular slideshow
    dm.stop_slideshow_countdown()
    time.sleep(0.5)

    status, state_resp = fetch_json(f"{FUNNEL_BASE}/slideshow/api/slideshow/state")
    state = state_resp.get("state", {})
    assert state.get("mode") == "slideshow"
    print("[PASS] 6d. Race cut-in stopped cleanly, regular slideshow resumed!")

    print("\n=========================================================")
    print(">>> ALL TAILSCALE FUNNEL SLIDESHOW & CUT-IN TESTS PASSED! <<<")
    print("=========================================================")

if __name__ == "__main__":
    main()
