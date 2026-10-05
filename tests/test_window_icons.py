import unittest
from unittest.mock import Mock
from backend.window_icons import WindowIcons, icon_sizes


class WindowIconTests(unittest.TestCase):
    def api(self, dpi):
        api = Mock()
        api.GetDpiForWindow.return_value = dpi
        api.IsWindow.return_value = True
        api.LoadImageW.side_effect = lambda instance, path, kind, x, y, flags: 1000+x
        return api

    def test_dpi_sizes(self):
        self.assertEqual(icon_sizes(96), (16,32))
        self.assertEqual(icon_sizes(144), (24,48))
        self.assertEqual(icon_sizes(192), (32,64))
        self.assertEqual(icon_sizes(240), (40,80))

    def test_sets_both_native_sizes_and_reuses_loaded_handles(self):
        api = self.api(192)
        manager = WindowIcons(api)
        with_icons = {}
        def send(hwnd, message, kind, value, flags, timeout, result):
            result._obj.value = with_icons.get(kind, 0)
            if message == 0x80:
                with_icons[kind] = value
            return 1
        api.SendMessageTimeoutW.side_effect = send
        self.assertTrue(manager.apply(42))
        self.assertEqual(with_icons, {0:1032,1:1064})
        self.assertEqual(api.LoadImageW.call_count, 2)
        self.assertTrue(manager.apply(42))
        self.assertEqual(api.LoadImageW.call_count, 2)
        # Browser replacing the small icon is repaired; DPI changes load new sizes.
        with_icons[0] = 999
        self.assertTrue(manager.apply(42))
        self.assertEqual(with_icons[0], 1032)
        api.GetDpiForWindow.return_value = 144
        self.assertTrue(manager.apply(42))
        self.assertEqual(with_icons, {0:1024,1:1048})

    def test_closed_and_unresponsive_windows_are_not_retried_forever(self):
        api = self.api(96)
        manager = WindowIcons(api)
        api.IsWindow.return_value = False
        self.assertFalse(manager.apply(42))
        api.LoadImageW.assert_not_called()
        api.IsWindow.return_value = True
        api.SendMessageTimeoutW.return_value = 0
        self.assertFalse(manager.apply(42))

    def test_missing_icon_does_not_send_invalid_handle(self):
        api = self.api(96)
        api.LoadImageW.side_effect = None
        api.LoadImageW.return_value = 0
        self.assertFalse(WindowIcons(api).apply(42))
        api.SendMessageTimeoutW.assert_not_called()
