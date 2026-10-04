import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from control_window import ControlWindow


class ControlWindowTests(unittest.TestCase):
    def test_app_launch_uses_fixed_local_url_and_separate_profile(self):
        with tempfile.TemporaryDirectory() as root:
            window = ControlWindow("http://127.0.0.1:15150", root)
            window.edge = Path("C:/Program Files/Edge/msedge.exe")
            with patch.object(window, "existing_window", return_value=None), patch("control_window.subprocess.Popen") as spawn:
                self.assertEqual(window.open()["mode"], "window")
                args = spawn.call_args.args[0]
                self.assertIn("--app=http://127.0.0.1:15150/?control=1", args)
                self.assertIn("--user-data-dir=" + str(Path(root)/".runtime"/"control-window-profile"), args)
                self.assertNotIn("shell", spawn.call_args.kwargs)

    def test_existing_window_is_restored_without_spawning(self):
        desktop = Mock()
        window = ControlWindow("http://127.0.0.1:15150", ".", desktop)
        with patch.object(window, "existing_window", return_value=42), patch("control_window.subprocess.Popen") as spawn:
            self.assertTrue(window.open()["reused"])
            desktop.u.ShowWindowAsync.assert_called_once_with(42, 9)
            desktop.u.SetForegroundWindow.assert_called_once_with(42)
            spawn.assert_not_called()

    def test_missing_edge_falls_back_to_webui(self):
        window = ControlWindow("http://127.0.0.1:15150", ".")
        window.edge = None
        with patch.object(window, "existing_window", return_value=None), patch("control_window.webbrowser.open") as browser:
            self.assertEqual(window.open()["mode"], "browser")
            browser.assert_called_once_with("http://127.0.0.1:15150/?control=1")
