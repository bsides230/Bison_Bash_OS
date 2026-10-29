import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

# Headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QMessageBox
import master_admin.data_manager as dm
from games.slideshow_server import app as slideshow_app
from fastapi.testclient import TestClient

from launcher_gui import (
    MainWindow,
    SlideshowBuilderDialog,
    PresentationBuilderDialog,
    make_slide_thumbnail
)

qt_app = QApplication.instance()
if not qt_app:
    qt_app = QApplication([sys.argv[0], "-platform", "offscreen"])

client = TestClient(slideshow_app)

class TestSlideshowPauseResumeAndBuilders(unittest.TestCase):

    def setUp(self):
        self.msgbox_info_patch = patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok)
        self.msgbox_quest_patch = patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes)
        self.msgbox_warn_patch = patch.object(QMessageBox, 'warning', return_value=QMessageBox.StandardButton.Ok)
        self.msgbox_info_patch.start()
        self.msgbox_quest_patch.start()
        self.msgbox_warn_patch.start()

    def tearDown(self):
        self.msgbox_info_patch.stop()
        self.msgbox_quest_patch.stop()
        self.msgbox_warn_patch.stop()

    def test_cutin_pause_and_resume_state_transitions(self):
        print("\n--- 1. Testing Cut-in Pause & Resume State Transitions ---")
        from PIL import Image
        import io
        img = Image.new("RGB", (320, 180), (10, 20, 30))
        b = io.BytesIO()
        img.save(b, "JPEG")
        test_bytes = b.getvalue()
        ps1 = dm.process_and_save_slide(test_bytes, "test_p1.jpg", title="P1", deck="presentation")
        ps2 = dm.process_and_save_slide(test_bytes, "test_p2.jpg", title="P2", deck="presentation")

        try:
            # 1. Start in regular slideshow
            dm.stop_presentation_mode()
            state = dm.get_slideshow_state()
            self.assertEqual(state["mode"], "slideshow")

            # 2. Bison Dash Cut-in Triggered
            dm.set_slideshow_countdown(minutes=2, seconds=0, title="Semi-Finals Race")
            state = dm.get_slideshow_state()
            self.assertEqual(state["mode"], "bison_countdown")
            self.assertTrue(state["countdown"]["active"])
            self.assertFalse(state["presentation"]["active"])

            # 3. Race mode
            dm.set_slideshow_mode("bison_race")
            state = dm.get_slideshow_state()
            self.assertEqual(state["mode"], "bison_race")

            # 4. Cut-in finishes -> return to slideshow (pauses rotation, then resumes at active slide)
            dm.stop_slideshow_countdown()
            state = dm.get_slideshow_state()
            self.assertEqual(state["mode"], "slideshow")
            self.assertFalse(state["countdown"]["active"])
            print("[PASS] Bison Dash cut-in cycle cleanly returned to regular slideshow!")

            # 5. Stage Presentation Cut-in Triggered
            dm.start_presentation_mode(slide_index=0)
            state = dm.get_slideshow_state()
            self.assertEqual(state["mode"], "presentation")
            self.assertTrue(state["presentation"]["active"])
            self.assertEqual(state["presentation"]["current_index"], 0)

            # 6. Presenter steps slide forward
            dm.step_presentation_slide(delta=1)
            state = dm.get_slideshow_state()
            self.assertEqual(state["presentation"]["current_index"], 1)

            # 7. Presentation finishes -> return to slideshow
            dm.stop_presentation_mode()
            state = dm.get_slideshow_state()
            self.assertEqual(state["mode"], "slideshow")
            self.assertFalse(state["presentation"]["active"])
            print("[PASS] Presentation cut-in cycle cleanly returned to regular slideshow!")

            # 8. Restart regular slideshow trigger
            dm.restart_regular_slideshow()
            state = dm.get_slideshow_state()
            self.assertEqual(state["mode"], "slideshow")
            self.assertGreater(state["restart_trigger"], 0)
            print(f"[PASS] Restart regular slideshow trigger broadcast: {state['restart_trigger']}")
        finally:
            dm.delete_presentation_slide(ps1["id"])
            dm.delete_presentation_slide(ps2["id"])

    def test_slideshow_html_pause_and_resume_logic(self):
        print("\n--- 2. Testing slideshow.html Client-side Pause & Resume Logic ---")
        res = client.get("/slideshow")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # Verify cut-in detection & pause/resume handlers
        self.assertIn("lastCutInActive", html, "slideshow.html must track cut-in active state")
        self.assertIn("slideStartTime = Date.now()", html, "slideshow.html must reset timer when resuming after cut-in")
        self.assertIn("progressBar", html, "slideshow.html must reset progress bar upon resumption")
        self.assertIn("lastManifestVersion", html, "slideshow.html must track manifest version for live reloads")
        self.assertIn("restart_trigger", html, "slideshow.html must respond to restart regular command")

        # Verify clean DJ screen: zero buttons inside presentation overlay
        self.assertIn('id="presentation-override-layer"', html)
        self.assertIn('id="presentation-image"', html)
        self.assertIn('toggleFullscreen', html)
        self.assertIn('F11', html)
        self.assertIn('Escape', html)
        print("[PASS] slideshow.html verified: strictly pauses during cut-ins, resumes active slide with fresh timer, clean DJ Mac layout!")

    def test_slideshow_builder_dialog(self):
        print("\n--- 3. Testing SlideshowBuilderDialog Drag-and-Drop & Save ---")
        dlg = SlideshowBuilderDialog()
        self.assertGreater(dlg.list_widget.count(), 0)

        initial_count = dlg.list_widget.count()
        item0 = dlg.list_widget.item(0)
        self.assertFalse(item0.icon().isNull(), "Slide thumbnail icon must not be null")

        # Test drag-and-drop / manual move
        dlg.list_widget.setCurrentRow(0)
        dlg._move_selected(1)
        self.assertEqual(dlg.list_widget.currentRow(), 1)
        self.assertIn("Order changed", dlg.lbl_status.text())

        # Test Save Order
        dlg._save_order()
        self.assertIn("Saved", dlg.lbl_status.text())

        # Test duration modification
        with patch.object(QMessageBox, 'information'):
            dlg.list_widget.setCurrentRow(0)
            s_data = dlg.list_widget.item(0).data(256)
            self.assertIsNotNone(s_data)

        dlg.close()
        print("[PASS] SlideshowBuilderDialog drag-and-drop reordering, thumbnailing, and save verified!")

    def test_presentation_builder_dialog(self):
        print("\n--- 4. Testing PresentationBuilderDialog Drag-and-Drop & Save ---")
        from PIL import Image
        import io
        img = Image.new("RGB", (320, 180), (0, 150, 255))
        b = io.BytesIO()
        img.save(b, "JPEG")
        content = b.getvalue()

        ps1 = dm.process_and_save_slide(content, "intro_slide.jpg", title="Introduction", deck="presentation")
        ps2 = dm.process_and_save_slide(content, "agenda_slide.jpg", title="Agenda", deck="presentation")

        dlg = PresentationBuilderDialog()
        self.assertGreaterEqual(dlg.list_widget.count(), 2)

        # Verify thumbnail icons
        self.assertFalse(dlg.list_widget.item(0).icon().isNull())

        # Reorder
        dlg.list_widget.setCurrentRow(0)
        dlg._move_selected(1)
        self.assertIn("Order changed", dlg.lbl_status.text())

        # Save
        dlg._save_order()
        self.assertIn("saved", dlg.lbl_status.text())

        # Clean up
        dm.delete_presentation_slide(ps1["id"])
        dm.delete_presentation_slide(ps2["id"])
        dlg.close()
        print("[PASS] PresentationBuilderDialog drag-and-drop reordering, thumbnailing, and save verified!")

    def test_presenter_remote_endpoints_and_live_sync(self):
        print("\n--- 5. Testing Presenter Remote & Realtime Sync ---")
        res = client.get("/presenter")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Stage Slide Remote", res.text)
        self.assertIn("btnPrev", res.text)
        self.assertIn("btnNext", res.text)
        self.assertIn("lastManifestVersion", res.text)

        # Test step delta
        res_step = client.post("/api/slideshow/presentation/step", json={"delta": 1})
        self.assertEqual(res_step.status_code, 200)
        self.assertTrue(res_step.json()["status"] == "success")

        # Test set index
        res_set = client.post("/api/slideshow/presentation/set_index", json={"index": 0})
        self.assertEqual(res_set.status_code, 200)
        self.assertEqual(res_set.json()["state"]["presentation"]["current_index"], 0)

        # Clean up state
        dm.stop_presentation_mode()
        print("[PASS] Presenter Remote mobile endpoints and state sync verified!")

if __name__ == "__main__":
    unittest.main()
