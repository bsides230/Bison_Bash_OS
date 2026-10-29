"""
Verification test for Native PyQt Stadium Slideshow & Projector Screen
"""
import sys
import io
import time
from pathlib import Path
from PIL import Image

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

import master_admin.data_manager as dm
from projector_screen import (
    NativeProjectorWindow,
    LeaderboardSlide,
    CustomImageSlide,
    WelcomeSlide,
    MobilePassQrSlide,
    GameStationsSlide,
    BisonCountdownSlide,
    generate_qr_pixmap
)

def test_native_projector():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    print("--- 1. Testing QR Code Generation for Mobile Pass ---")
    qr_pixmap = generate_qr_pixmap("http://192.168.1.50:8009/", size=200)
    assert not qr_pixmap.isNull(), "QR Pixmap should be valid"
    assert qr_pixmap.width() == 200 and qr_pixmap.height() == 200
    print("[OK] QR Pixmap generated successfully: 200x200")

    print("--- 2. Instantiating NativeProjectorWindow ---")
    win = NativeProjectorWindow(lan_ip="192.168.1.50")
    assert win is not None
    assert win.stack.count() >= 3, "Stack should contain override slides and playlist slides"
    print(f"[OK] NativeProjectorWindow instantiated with {len(win.playlist)} playlist slides")

    print("--- 3. Verifying Leaderboard Slide in Regular Mix ---")
    leaderboard_entries = [p for p in win.playlist if p.get("type") == "leaderboard"]
    assert len(leaderboard_entries) > 0, "Leaderboard slide must be in regular playlist mix!"
    lb_widget = leaderboard_entries[0]["widget"]
    assert isinstance(lb_widget, LeaderboardSlide)
    lb_widget.on_activate() # Executes dynamic data query
    print(f"[OK] Leaderboard slide present in mix and on_activate() executed cleanly: {lb_widget}")

    print("--- 4. Testing Custom 1920x1080 Uploaded Slide Integration ---")
    dummy_img = Image.new("RGB", (800, 600), color=(0, 180, 240))
    buf = io.BytesIO()
    dummy_img.save(buf, format="PNG")
    new_slide = dm.process_and_save_slide(buf.getvalue(), "native_test.png", "PyQt Native Sponsor")
    slide_id = new_slide["id"]
    save_path = dm.SLIDES_DIR / new_slide["filename"]
    assert save_path.exists()

    win.reload_manifest()
    found_custom = [p for p in win.playlist if p["title"] == "PyQt Native Sponsor"]
    assert len(found_custom) == 1, "Custom slide should be loaded into NativeProjectorWindow playlist"
    custom_widget = found_custom[0]["widget"]
    assert isinstance(custom_widget, CustomImageSlide)
    print("[OK] Custom 1920x1080 slide loaded into native presentation stack")

    print("--- 5. Testing Slide Advancement (Next/Prev) ---")
    initial_idx = win.current_slide_idx
    win.next_slide()
    assert win.current_slide_idx == (initial_idx + 1) % len(win.playlist)
    win.prev_slide()
    assert win.current_slide_idx == initial_idx
    print("[OK] Slide navigation next/prev verified")

    print("--- 6. Testing Manual Bison Dash Race Countdown Override ---")
    # Operator starts countdown via data manager
    cd_state = dm.set_slideshow_countdown(minutes=2, seconds=30, title="Bison Finals Heat 1")
    win._poll_arena_state()

    # Verify native window immediately cuts in to the countdown slide!
    assert win.stack.currentWidget() == win.countdown_slide, "Window must cut to Countdown Slide!"
    assert win.countdown_slide.lbl_race_title.text() == "Bison Finals Heat 1"
    clock_text = win.countdown_slide.lbl_timer_clock.text()
    assert ":" in clock_text, f"Clock must display MM:SS, got {clock_text}"
    assert "RACE COUNTDOWN" in win.header.lbl_mode_badge.text()
    print(f"[OK] Native Projector cut-in verified! Timer: {clock_text}, Title: {win.countdown_slide.lbl_race_title.text()}")

    print("--- 7. Testing Pre-Race and Live Race Staged Slides ---")
    dm.set_slideshow_mode("bison_prerace")
    win._poll_arena_state()
    assert win.stack.currentWidget() == win.prerace_slide
    print("[OK] Pre-Race lineup slide verified")

    dm.set_slideshow_mode("bison_race")
    win._poll_arena_state()
    assert win.stack.currentWidget() == win.liverace_slide
    print("[OK] Live Race sprint slide verified")

    print("--- 8. Testing Return to Regular Rotation ---")
    dm.stop_slideshow_countdown()
    win._poll_arena_state()
    assert win.stack.currentWidget() in [p["widget"] for p in win.playlist], "Must return to regular rotation"
    assert "ROTATING SLIDESHOW" in win.header.lbl_mode_badge.text()
    print("[OK] Returned to regular slideshow rotation")

    print("--- 9. Cleaning up Test Artifacts ---")
    dm.delete_slide(slide_id)
    win.close()
    print("[OK] Cleanup complete")

    print("\n==============================================")
    print(">>> ALL NATIVE PROJECTOR TESTS PASSED 100% <<<")
    print("==============================================")

if __name__ == "__main__":
    test_native_projector()
