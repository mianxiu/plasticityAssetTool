import threading
import unittest
from unittest.mock import Mock
from backend.library_launcher import LibraryLauncher


class ToggleTests(unittest.TestCase):
    def launcher(self):
        launcher = LibraryLauncher.__new__(LibraryLauncher)
        launcher.operation_lock = threading.RLock()
        launcher.targets = {42, 43}
        launcher.panel = Mock(hwnd=7, target=42, visible=False)
        def show(target_id):
            launcher.panel.target = int(target_id[5:])
            launcher.panel.visible = True
        def hide():
            launcher.panel.visible = False
        launcher._open = Mock(side_effect=show)
        launcher.panel.dismiss.side_effect = hide
        return launcher

    def test_repeated_toggles_reuse_panel_and_close_every_second_press(self):
        launcher = self.launcher()
        for index in range(20):
            self.assertEqual(launcher.toggle('hwnd:42'), index % 2 == 0)
            self.assertEqual(launcher.panel.visible, index % 2 == 0)
        self.assertEqual(launcher._open.call_count, 10)
        self.assertEqual(launcher.panel.dismiss.call_count, 10)

    def test_panel_foreground_routes_tab_back_to_its_model(self):
        launcher = self.launcher()
        self.assertIsNone(launcher.hotkey_target(7))
        launcher.toggle('hwnd:42')
        self.assertEqual(launcher.hotkey_target(7), 42)
        self.assertIsNone(launcher.hotkey_target(99))
        launcher.targets.remove(42)
        self.assertIsNone(launcher.hotkey_target(7))

    def test_different_model_retargets_instead_of_closing_other_models_panel(self):
        launcher = self.launcher()
        launcher.toggle('hwnd:42')
        self.assertTrue(launcher.toggle('hwnd:43'))
        self.assertEqual(launcher.panel.target, 43)
        launcher.panel.dismiss.assert_not_called()

    def test_hidden_panel_reopens_after_switching_apps_or_esc(self):
        launcher = self.launcher()
        launcher.toggle('hwnd:42')
        launcher.panel.dismiss()
        self.assertTrue(launcher.toggle('hwnd:42'))
