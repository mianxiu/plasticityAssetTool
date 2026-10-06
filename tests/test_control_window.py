import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from backend.control_window import ControlWindow


class ControlWindowTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows window enumeration')
    def test_library_window_is_not_reused_as_control_center(self):
        desktop = Mock()
        titles = {41: 'plasticity asset tool — component library', 42: 'plasticity asset tool — control center'}
        desktop.u.IsWindowVisible.return_value = True
        desktop.u.GetWindowTextW.side_effect = lambda hwnd, buffer, size: setattr(buffer, 'value', titles[hwnd])
        desktop.process_path.return_value = 'C:/Program Files/Edge/msedge.exe'
        desktop.u.EnumWindows.side_effect = lambda callback, arg: [callback(hwnd, arg) for hwnd in titles]
        self.assertEqual(ControlWindow('http://127.0.0.1:15150', '.', desktop).existing_window(), 42)

    def test_app_launch_uses_fixed_local_url_and_separate_profile(self):
        with tempfile.TemporaryDirectory() as root:
            window = ControlWindow("http://127.0.0.1:15150", root)
            window.edge = Path("C:/Program Files/Edge/msedge.exe")
            with patch.object(window, "existing_window", return_value=None), patch("backend.control_window.subprocess.Popen") as spawn:
                self.assertEqual(window.open()["mode"], "window")
                args = spawn.call_args.args[0]
                self.assertIn("--app=http://127.0.0.1:15150/?control=1", args)
                self.assertIn("--user-data-dir=" + str(Path(root)/".runtime"/"control-window-profile"), args)
                self.assertIn("--window-size=960,720", args)
                self.assertNotIn("shell", spawn.call_args.kwargs)

    def test_existing_window_is_restored_without_spawning(self):
        desktop = Mock()
        window = ControlWindow("http://127.0.0.1:15150", ".", desktop)
        with patch.object(window, "existing_window", return_value=42), patch.object(window, '_watch_icons'), patch.object(window.icons, 'apply') as icons, patch("backend.control_window.subprocess.Popen") as spawn:
            self.assertTrue(window.open()["reused"])
            desktop.u.ShowWindowAsync.assert_called_once_with(42, 9)
            desktop.u.SetForegroundWindow.assert_called_once_with(42)
            spawn.assert_not_called()
            icons.assert_called_once_with(42)

    def test_missing_edge_falls_back_to_webui(self):
        window = ControlWindow("http://127.0.0.1:15150", ".")
        window.edge = None
        with patch.object(window, "existing_window", return_value=None), patch("backend.control_window.webbrowser.open") as browser:
            self.assertEqual(window.open()["mode"], "browser")
            browser.assert_called_once_with("http://127.0.0.1:15150/?control=1")
