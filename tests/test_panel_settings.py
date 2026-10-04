import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from panel_settings import PanelSettings
from test_service_control import make_application


class PanelSettingsTests(unittest.TestCase):
    def test_default_save_restart_and_invalid_value(self):
        with tempfile.TemporaryDirectory() as root:
            settings = PanelSettings(root)
            self.assertEqual(settings.snapshot(), {"position": "fixed", "sidebar_mode": "fixed"})
            settings.update("cursor")
            self.assertEqual(PanelSettings(root).position, "cursor")
            with self.assertRaises(ValueError):
                settings.update("other")
            self.assertEqual(PanelSettings(root).position, "cursor")
            settings.update("fixed")
            self.assertEqual(PanelSettings(root).position, "fixed")

    def test_failed_save_keeps_existing_preference(self):
        with tempfile.TemporaryDirectory() as root:
            settings = PanelSettings(root)
            with patch.object(Path, "replace", side_effect=OSError("write failed")):
                with self.assertRaises(OSError):
                    settings.update("cursor")
            self.assertEqual(settings.position, "fixed")

    def test_sidebar_update_preserves_position_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as root:
            settings = PanelSettings(root)
            settings.update("cursor")
            settings.update(sidebar_mode="hover")
            self.assertEqual(PanelSettings(root).snapshot(), {"position":"cursor", "sidebar_mode":"hover"})
            settings.update("fixed")
            self.assertEqual(settings.sidebar_mode, "hover")
            with self.assertRaises(ValueError):
                settings.update(sidebar_mode="invalid")
            self.assertEqual(PanelSettings(root).sidebar_mode, "hover")


class PanelControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_control_and_component_clients_share_persistent_setting(self):
        with tempfile.TemporaryDirectory() as root:
            app = make_application(root)
            result = await app.dispatch("service.panel_settings", {"position": "cursor"})
            self.assertEqual(result["panel_settings"]["position"], "cursor")
            self.assertEqual((await app.dispatch("state", {}))["panel_settings"]["position"], "cursor")
            self.assertEqual((await app.dispatch("service.status", {}))["panel_settings"]["position"], "cursor")
            self.assertEqual(PanelSettings(root).position, "cursor")
            await app.dispatch("service.panel_settings", {"sidebar_mode":"hover"})
            self.assertEqual((await app.dispatch("state", {}))["panel_settings"], {"position":"cursor", "sidebar_mode":"hover"})
