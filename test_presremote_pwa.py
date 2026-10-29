import unittest
from fastapi.testclient import TestClient
from pathlib import Path

from games.slideshow_server import app as slideshow_app
from games.presremote_server import app as presremote_app
from master_admin.main import app as master_admin_app
import master_admin.data_manager as dm

class TestPresRemotePWA(unittest.TestCase):
    def setUp(self):
        self.slideshow_client = TestClient(slideshow_app)
        self.presremote_client = TestClient(presremote_app)
        self.admin_client = TestClient(master_admin_app)

    def test_presremote_dedicated_server_port_8011(self):
        # Dedicated Port 8011 root '/' MUST serve PresRemote directly!
        res_root = self.presremote_client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertIn("PresRemote", res_root.text)
        self.assertIn("Stage Slide Remote", res_root.text)
        self.assertNotIn("Live Stadium Projector", res_root.text)

        # Health endpoint
        res_health = self.presremote_client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["service"], "presremote_service")
        self.assertEqual(res_health.json()["port"], 8011)

        # Slide APIs on 8011
        res_pres = self.presremote_client.get("/api/slides/presentation")
        self.assertEqual(res_pres.status_code, 200)

        res_state = self.presremote_client.get("/api/slideshow/state")
        self.assertEqual(res_state.status_code, 200)

    def test_presremote_route_slideshow_server(self):
        res = self.slideshow_client.get("/presremote")
        self.assertEqual(res.status_code, 200)
        self.assertIn("PresRemote", res.text)
        self.assertIn("Stage Slide Remote", res.text)
        self.assertIn("/presremote.webmanifest", res.text)
        self.assertIn("/presremote-sw.js", res.text)
        self.assertIn("btnNext", res.text)
        self.assertIn("btnPrev", res.text)
        self.assertIn("DEFAULT_REHEARSAL_SLIDES", res.text)
        self.assertIn("toggleFullscreen", res.text)
        self.assertIn("blankCard", res.text)

    def test_presremote_route_master_admin(self):
        res = self.admin_client.get("/presremote")
        self.assertEqual(res.status_code, 200)
        self.assertIn("PresRemote", res.text)
        self.assertIn("/presremote.webmanifest", res.text)

    def test_presremote_manifest(self):
        for client in [self.slideshow_client, self.admin_client]:
            res = client.get("/presremote.webmanifest")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["name"], "PresRemote - Stage Slide Controller")
            self.assertEqual(data["short_name"], "PresRemote")
            self.assertEqual(data["start_url"], "/presremote")
            self.assertEqual(data["display"], "standalone")
            self.assertTrue(len(data["icons"]) >= 2)

    def test_presremote_service_worker(self):
        for client in [self.slideshow_client, self.admin_client]:
            res = client.get("/presremote-sw.js")
            self.assertEqual(res.status_code, 200)
            self.assertIn("presremote-v1.0.0", res.text)
            self.assertIn("addEventListener", res.text)

    def test_pwa_icons_exist(self):
        img_dir = Path("master_admin/static/img")
        self.assertTrue((img_dir / "presremote-icon.svg").exists(), "SVG icon must exist")
        self.assertTrue((img_dir / "presremote-icon-192.png").exists(), "192px PNG icon must exist")
        self.assertTrue((img_dir / "presremote-icon-512.png").exists(), "512px PNG icon must exist")
        self.assertTrue((img_dir / "apple-touch-icon.png").exists(), "Apple touch icon must exist")

    def test_rehearsal_and_cutin_state_flow(self):
        # 1. Initially mode is slideshow
        dm.stop_presentation_mode()
        state = dm.get_slideshow_state()
        self.assertEqual(state.get("mode"), "slideshow")

        # 2. Presenter triggers stage broadcast via start endpoint
        res_start = self.slideshow_client.post("/api/slideshow/presentation/start", json={"slide_index": 0})
        self.assertEqual(res_start.status_code, 200)
        self.assertTrue(res_start.json()["state"]["presentation"]["active"])

        # 3. Presenter steps slide
        res_step = self.slideshow_client.post("/api/slideshow/presentation/step", json={"delta": 1})
        self.assertEqual(res_step.status_code, 200)

        # 4. Presenter stops presentation cut-in
        res_stop = self.slideshow_client.post("/api/slideshow/presentation/stop")
        self.assertEqual(res_stop.status_code, 200)
        self.assertFalse(res_stop.json()["state"]["presentation"]["active"])

if __name__ == "__main__":
    unittest.main()
