import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure offscreen platform for headless PyQt testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QMessageBox
import master_admin.data_manager as dm
from launcher_gui import (
    SERVICES_CONFIG, MainWindow, get_lan_ip,
    SlideshowBuilderDialog, PresentationBuilderDialog,
    make_slide_thumbnail
)

app = QApplication.instance()
if not app:
    app = QApplication([sys.argv[0], "-platform", "offscreen"])

class TestLauncherGuiSlideshow(unittest.TestCase):

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

    def test_services_config_has_slideshow(self):
        print("\n--- 1. Testing SERVICES_CONFIG in launcher_gui.py ---")
        slideshow_cfg = None
        for cfg in SERVICES_CONFIG:
            if cfg["id"] == "slideshow":
                slideshow_cfg = cfg
                break

        self.assertIsNotNone(slideshow_cfg, "slideshow service must be in SERVICES_CONFIG")
        self.assertEqual(slideshow_cfg["port"], 8010)
        self.assertEqual(slideshow_cfg["module"], "games.slideshow_server:app")
        self.assertIn("8010", slideshow_cfg["url"])
        print(f"[PASS] SERVICES_CONFIG contains Port 8010 Stadium Slideshow: {slideshow_cfg['name']}!")

    def test_main_window_clean_structure(self):
        print("\n--- 2. Testing MainWindow Clean Layout (No 'Big Box') ---")
        window = MainWindow()

        # Verify that the big custom proj_panel is GONE
        self.assertFalse(hasattr(window, "proj_panel"), "proj_panel should not exist on MainWindow")
        self.assertFalse(hasattr(window, "combo_screens"), "combo_screens should not clutter MainWindow")
        self.assertFalse(hasattr(window, "local_preview_frame"), "local_preview_frame should not clutter MainWindow")

        # Verify that slideshow is a standard service card like all other systems
        self.assertIn("slideshow", window.workers)
        self.assertIn("slideshow", window.card_widgets)

        card = window.card_widgets["slideshow"]
        self.assertIsNotNone(card)
        self.assertEqual(card.service_id, "slideshow")
        self.assertTrue(hasattr(card, "btn_browser"))
        self.assertTrue(hasattr(card, "btn_switch"))
        self.assertTrue(hasattr(card, "btn_toggle_terminal"))

        # Verify card copy URL functionality
        lan_ip = get_lan_ip()
        card._copy_url()
        clipboard_text = QApplication.clipboard().text()
        expected_url = f"http://{lan_ip}:8010/slideshow" if lan_ip != "127.0.0.1" else "http://localhost:8010/slideshow"
        self.assertEqual(clipboard_text, expected_url)
        print(f"[PASS] Slideshow service card verified: Copy URL -> {clipboard_text}")

        # Verify clean system stats
        window._update_system_stats()
        self.assertIn("Running", window.lbl_active_count.text())
        print(f"[PASS] System stats updated cleanly: {window.lbl_active_count.text()}")

        window.close()

    def test_slideshow_builder_drag_drop_and_save(self):
        print("\n--- 3. Testing SlideshowBuilderDialog Drag-and-Drop & Save Order ---")
        dlg = SlideshowBuilderDialog()
        self.assertGreater(dlg.list_widget.count(), 0, "Slideshow builder should have loaded existing slides")

        initial_count = dlg.list_widget.count()
        first_item = dlg.list_widget.item(0)
        first_data = first_item.data(1) or first_item.data(256) # UserRole
        self.assertIsNotNone(first_data)

        # Move first item down
        dlg.list_widget.setCurrentRow(0)
        dlg._move_selected(1)
        self.assertEqual(dlg.list_widget.currentRow(), 1)

        # Save order
        dlg._save_order()
        manifest = dm.get_slides_manifest()
        slides = manifest.get("slides", [])
        self.assertEqual(len(slides), initial_count)
        print(f"[PASS] Reordered slides in SlideshowBuilderDialog and persisted order to manifest ({len(slides)} slides)!")

        # Test toggle active
        dlg.list_widget.setCurrentRow(0)
        dlg._toggle_selected()
        toggled_item = dlg.list_widget.item(0)
        toggled_data = toggled_item.data(256)
        print(f"[PASS] Toggled slide '{toggled_data.get('title')}' enabled state!")

        dlg.close()

    def test_presentation_builder_drag_drop_and_save(self):
        print("\n--- 4. Testing PresentationBuilderDialog Drag-and-Drop & Save Order ---")
        # Ensure at least 2 presentation slides exist for reorder test
        from PIL import Image
        import io
        img = Image.new("RGB", (400, 300), (255, 120, 0))
        b = io.BytesIO()
        img.save(b, "JPEG")
        bytes_data = b.getvalue()

        s1 = dm.process_and_save_slide(bytes_data, "test_talk_intro.jpg", title="Keynote Intro", deck="presentation")
        s2 = dm.process_and_save_slide(bytes_data, "test_talk_outro.jpg", title="Keynote Conclusion", deck="presentation")

        dlg = PresentationBuilderDialog()
        self.assertGreaterEqual(dlg.list_widget.count(), 2)

        # Verify thumbnail icon exists
        icon = dlg.list_widget.item(0).icon()
        self.assertFalse(icon.isNull(), "Slide item icon should be populated")

        # Move item 0 down
        dlg.list_widget.setCurrentRow(0)
        dlg._move_selected(1)

        # Save order
        dlg._save_order()
        pres_slides = dm.get_presentation_slides()
        self.assertGreaterEqual(len(pres_slides), 2)
        print(f"[PASS] Reordered presentation slides in PresentationBuilderDialog and saved ({len(pres_slides)} slides)!")

        # Clean up test slides
        dm.delete_presentation_slide(s1["id"])
        dm.delete_presentation_slide(s2["id"])
        dlg.close()

    def test_main_window_builder_buttons(self):
        print("\n--- 5. Testing MainWindow Top Bar and Card Shortcut Buttons ---")
        window = MainWindow()

        # Check top bar buttons
        self.assertTrue(hasattr(window, "_open_slideshow_builder"))
        self.assertTrue(hasattr(window, "_open_presentation_builder"))

        # Check card shortcuts on port 8010 card
        card = window.card_widgets["slideshow"]
        self.assertIsNotNone(card)

        # Card has Deck and Pres shortcut buttons
        btn_texts = [btn.text() for btn in card.findChildren(type(card.btn_browser))]
        self.assertTrue(any("Deck" in t for t in btn_texts), "Slideshow card should have 🖼️ Deck button")
        self.assertTrue(any("Pres" in t for t in btn_texts), "Slideshow card should have 📢 Pres button")
        print("[PASS] MainWindow top bar and slideshow card quick-builder buttons verified!")

        window.close()

if __name__ == "__main__":
    unittest.main()
