import threading
import unittest
from unittest.mock import Mock

from native_panel import NativePanel, panel_bounds


class PanelTests(unittest.TestCase):
    def panel(self):
        panel = NativePanel.__new__(NativePanel)
        panel.desktop = Mock()
        panel.u = Mock()
        panel.hwnd, panel.target = 7, 42
        panel.saved = (0x00CF0000, 0x40000, 0)
        panel.bounds, panel.visible = None, True
        panel.lock = threading.RLock()
        panel.u.IsWindow.return_value = True
        panel.u.IsIconic.return_value = False
        panel.u.GetForegroundWindow.return_value = 42
        def rectangle(hwnd, pointer):
            pointer._obj.right, pointer._obj.bottom = 1200, 900
            return True
        def screen(hwnd, pointer):
            pointer._obj.x, pointer._obj.y = 100, 200
            return True
        panel.u.GetClientRect.side_effect = rectangle
        panel.u.ClientToScreen.side_effect = screen
        panel.u.SetWindowPos.return_value = True
        panel.gdi = Mock()
        panel.u.SetThreadDpiAwarenessContext.return_value = None
        panel.u.GetDpiForWindow.return_value = 96
        panel.u.GetSystemMetricsForDpi.side_effect = lambda index, dpi: {32:8, 92:4, 4:23}[index]
        panel.gdi.CreateRectRgn.return_value = 123
        panel.u.SetWindowRgn.return_value = 1
        panel.u.GetWindowRgnBox.return_value = 0
        return panel

    def test_bounds_fit_even_small_cad_windows(self):
        for width, height in ((1600, 1000), (900, 600), (240, 120), (1, 1)):
            x, y, w, h = panel_bounds(width, height, (100, 200))
            self.assertGreaterEqual(x, 100)
            self.assertGreaterEqual(y, 200)
            self.assertLessEqual(x+w, 100+width)
            self.assertLessEqual(y+h, 200+height)
        self.assertEqual(panel_bounds(3000, 2000, scale=2), (380, 240, 2240, 1520))

    def test_failed_clipping_releases_region(self):
        panel = self.panel()
        panel.u.SetWindowRgn.return_value = 0
        with self.assertRaises(OSError):
            panel.position()
        panel.gdi.DeleteObject.assert_called_once_with(123)

    def test_existing_clip_does_not_force_repaint(self):
        panel = self.panel()
        def region(hwnd, pointer):
            pointer._obj.left, pointer._obj.top = 12, 35
            pointer._obj.right, pointer._obj.bottom = 1132, 795
            return 2
        panel.u.GetWindowRgnBox.side_effect = region
        panel.position()
        panel.gdi.CreateRectRgn.assert_not_called()

    def test_attachment_changes_owner_and_removes_frame(self):
        panel = self.panel()
        panel.attach(7, 43)
        panel.desktop.validate.assert_called_once_with(43)
        panel.u.SetWindowLongPtrW.assert_any_call(7, -16, 0x80000000)
        panel.u.SetWindowLongPtrW.assert_any_call(7, -20, 0x80)
        panel.u.SetWindowLongPtrW.assert_any_call(7, -8, 43)
        self.assertEqual(panel.target, 43)

    def test_follows_cad_bounds_without_repeated_resize(self):
        panel = self.panel()
        panel.tick()
        panel.u.SetWindowPos.assert_called_once_with(7, None, 128, 259, 1144, 807, 0x34)
        panel.gdi.CreateRectRgn.assert_called_once_with(12, 35, 1132, 795)
        panel.tick()
        self.assertEqual(panel.u.SetWindowPos.call_count, 1)

    def test_switching_to_other_app_hides_panel_without_stealing_focus(self):
        panel = self.panel()
        panel.u.GetForegroundWindow.return_value = 99
        panel.tick()
        panel.u.ShowWindowAsync.assert_called_once_with(7, 0)
        panel.u.SetForegroundWindow.assert_not_called()
        self.assertFalse(panel.visible)

    def test_insert_minimization_is_treated_as_dismissal(self):
        panel = self.panel()
        panel.u.IsIconic.side_effect = lambda hwnd: hwnd == 7
        panel.tick()
        self.assertFalse(panel.visible)

    def test_restore_returns_original_style_and_owner(self):
        panel = self.panel()
        panel.restore()
        for index, value in ((-16, 0xCF0000), (-20, 0x40000), (-8, 0)):
            panel.u.SetWindowLongPtrW.assert_any_call(7, index, value)
        self.assertIsNone(panel.hwnd)

    def test_dismiss_returns_focus_to_target(self):
        panel = self.panel()
        panel.dismiss()
        panel.desktop.activate.assert_called_once_with(42)
        self.assertFalse(panel.visible)
