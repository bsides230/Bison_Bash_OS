import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import io

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QMessageBox
import master_admin.data_manager as dm
from games.slideshow_server import app as slideshow_app
from fastapi.testclient import TestClient

from launcher_gui import (
    MainWindow,
    SlideshowBuilderDialog
)

qt_app = QApplication.instance()
if not qt_app:
    qt_app = QApplication([sys.argv[0], "-platform", "offscreen"])

client = TestClient(slideshow_app)

class TestSlideshowBrandingAndCleanUI(unittest.TestCase):

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

    def test_clean_hud_and_bottom_nav_elements_removed(self):
        print("\n--- 1. Testing Removal of 'Live Stadium Projector', Nav Hint, and Slide Dots ---")
        res = client.get("/slideshow")
        self.assertEqual(res.status_code, 200)
        html = res.text

        # 1. "Live Stadium Projector" words removed
        self.assertNotIn("Live Stadium Projector", html, "'Live Stadium Projector' must be removed from slideshow.html")
        self.assertNotIn("hud-subtitle", html, "hud-subtitle element should not exist in DOM")

        # 2. Navigation stuff on bottom right removed
        self.assertNotIn("Press [Space] to pause", html, "Space/arrow key hint text must be removed")
        self.assertNotIn('class="nav-hint"', html, "nav-hint class must be removed from bottomNav")

        # 3. Slide thing on bottom left removed
        self.assertNotIn('id="slideDots"', html, "slideDots element must be removed from bottomNav")

        # 4. Progress bar remains centered
        self.assertIn('id="progressBar"', html, "progressBar should remain intact")
        self.assertIn('class="progress-bar-container"', html)
        print("[PASS] Cleaned slideshow display: subtitle words, bottom right nav hint, and bottom left dots removed!")

    def test_bison_logo_100x100_placeholder_and_upload(self):
        print("\n--- 2. Testing 100x100 Bison Logo PNG, Placeholder, and Upload API ---")
        logo_path = dm.STATIC_IMG_DIR / "bison_logo.png"
        placeholder_path = dm.STATIC_IMG_DIR / "bison_placeholder.png"

        self.assertTrue(logo_path.exists(), "Default 100x100 bison_logo.png must exist")
        self.assertTrue(placeholder_path.exists(), "Default 100x100 bison_placeholder.png must exist")

        with Image.open(logo_path) as img:
            self.assertEqual(img.size, (100, 100), "bison_logo.png must be exactly 100x100")
            self.assertEqual(img.mode, "RGBA")

        # Verify slideshow.html uses <img> tag with 100x100 source
        res = client.get("/slideshow")
        self.assertIn('id="hudLogoImg"', res.text)
        self.assertIn('class="hud-logo-img"', res.text)
        self.assertIn('/static/img/bison_logo.png', res.text)

        # Test upload new custom logo (creates crisp 100x100)
        test_img = Image.new("RGBA", (300, 300), (255, 215, 0, 255))
        b = io.BytesIO()
        test_img.save(b, "PNG")
        raw_bytes = b.getvalue()

        branding = dm.save_custom_logo(raw_bytes, "custom_sponsor_logo.png")
        self.assertIn("logo_url", branding)
        with Image.open(logo_path) as uploaded_img:
            self.assertEqual(uploaded_img.size, (100, 100), "Uploaded logo must be formatted to 100x100")

        # Test HTTP upload API on Port 8010
        files = {"file": ("api_logo.png", raw_bytes, "image/png")}
        res_upload = client.post("/api/slides/upload_logo", files=files)
        self.assertEqual(res_upload.status_code, 200)
        self.assertTrue(res_upload.json()["status"] == "success")

        # Reset to placeholder
        dm.reset_custom_logo()
        self.assertTrue(logo_path.exists())
        print("[PASS] 100x100 Bison Logo PNG placeholder, resizing, and upload API verified!")

    def test_branding_toggles_for_title_and_clock(self):
        print("\n--- 3. Testing Toggles for Techlahoma Title and Clock Pill ---")
        # 1. Defaults should both be True
        branding = dm.get_slideshow_branding()
        self.assertTrue(branding.get("show_header_title", True), "show_header_title should be True by default")
        self.assertTrue(branding.get("show_clock", True), "show_clock should be True by default")

        # 2. Toggle off Title
        updated = dm.set_slideshow_branding(show_header_title=False, show_clock=True)
        self.assertFalse(updated["show_header_title"])
        self.assertTrue(updated["show_clock"])

        # 3. Toggle off Clock
        updated = dm.set_slideshow_branding(show_header_title=True, show_clock=False)
        self.assertTrue(updated["show_header_title"])
        self.assertFalse(updated["show_clock"])

        # 4. HTTP API test for branding
        res_get = client.get("/api/slides/branding")
        self.assertEqual(res_get.status_code, 200)

        res_post = client.post("/api/slides/branding", json={"show_header_title": False, "show_clock": False})
        self.assertEqual(res_post.status_code, 200)
        data = res_post.json()["branding"]
        self.assertFalse(data["show_header_title"])
        self.assertFalse(data["show_clock"])

        # 5. Restore defaults (both True)
        dm.set_slideshow_branding(show_header_title=True, show_clock=True)

        # 6. Verify slideshow.html has DOM elements and applyBranding logic
        res = client.get("/slideshow")
        self.assertIn('id="hudBrand"', res.text)
        self.assertIn('id="hudClockContainer"', res.text)
        self.assertIn('applyBranding', res.text)
        print("[PASS] Branding toggles for Techlahoma Title & Clock Pill verified: default ON, toggleable OFF, and live sync!")

    def test_gui_slideshow_builder_controls(self):
        print("\n--- 4. Testing PyQt SlideshowBuilderDialog Controls & Service Card Button ---")
        dlg = SlideshowBuilderDialog()

        # Check logo preview & controls exist
        self.assertTrue(hasattr(dlg, "lbl_logo_preview"))
        self.assertFalse(dlg.lbl_logo_preview.pixmap().isNull(), "Logo preview pixmap should be loaded")

        # Check checkboxes exist and default to checked
        self.assertTrue(hasattr(dlg, "chk_show_title"))
        self.assertTrue(hasattr(dlg, "chk_show_clock"))
        self.assertTrue(dlg.chk_show_title.isChecked(), "Title checkbox should be checked by default")
        self.assertTrue(dlg.chk_show_clock.isChecked(), "Clock checkbox should be checked by default")

        # Toggle checkboxes
        dlg.chk_show_title.setChecked(False)
        self.assertFalse(dm.get_slideshow_branding()["show_header_title"])
        dlg.chk_show_title.setChecked(True)
        self.assertTrue(dm.get_slideshow_branding()["show_header_title"])

        dlg.close()

        # Check ServiceCardWidget has the Logo button
        window = MainWindow()
        card = window.card_widgets["slideshow"]
        btn_texts = [btn.text() for btn in card.findChildren(type(card.btn_browser))]
        self.assertTrue(any("Logo" in t for t in btn_texts), "Slideshow card must have 🦬 Logo button")
        window.close()
        print("[PASS] PyQt GUI SlideshowBuilderDialog branding controls & MainWindow card logo button verified!")

if __name__ == "__main__":
    unittest.main()
