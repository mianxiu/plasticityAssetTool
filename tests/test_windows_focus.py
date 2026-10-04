import unittest
from unittest.mock import Mock, patch

from windows_bridge import WindowsBridge


class FocusTests(unittest.TestCase):
    def test_last_cad_window_survives_webui_focus_and_is_removed_when_closed(self):
        bridge=WindowsBridge.__new__(WindowsBridge)
        bridge.u=Mock();bridge.last_active_hwnd=None
        bridge.is_model_window=Mock(side_effect=lambda hwnd:hwnd in (42,43))
        bridge.u.IsWindow.return_value=True
        bridge.u.GetForegroundWindow.return_value=42
        self.assertEqual(bridge.active_window(),42)
        bridge.u.GetForegroundWindow.return_value=43
        self.assertEqual(bridge.active_window(),43)
        bridge.u.GetForegroundWindow.return_value=7
        self.assertEqual(bridge.active_window(),43)
        bridge.u.IsWindow.return_value=False
        self.assertIsNone(bridge.active_window())

    def test_console_or_other_process_cannot_receive_model_shortcuts(self):
        bridge = WindowsBridge.__new__(WindowsBridge)
        bridge.process_path = Mock(return_value="C:/Plasticity/Plasticity.exe")
        bridge.u = Mock()
        bridge.u.IsWindow.return_value = True
        for window_class, accepted in [("ConsoleWindowClass", False), ("#32770", False), ("Chrome_WidgetWin_1", True)]:
            with self.subTest(window_class=window_class):
                def class_name(hwnd, buffer, length):
                    buffer.value = window_class
                bridge.u.GetClassNameW.side_effect = class_name
                self.assertEqual(bridge.is_model_window(42), accepted)
                if accepted:
                    bridge.validate(42)
                else:
                    with self.assertRaises(ValueError):
                        bridge.shortcut(42, "ctrl+shift+v")
                    bridge.u.SendInput.assert_not_called()
        bridge.process_path.return_value = "C:/Other/Other.exe"
        self.assertFalse(bridge.is_model_window(42))

    def bridge(self, title="Plasticity 模型组件库", process="C:/Edge/msedge.exe", succeeds=True):
        bridge = WindowsBridge.__new__(WindowsBridge)
        bridge.validate = Mock()
        bridge.process_path = Mock(return_value=process)
        bridge.u = Mock()
        bridge.u.foreground = 7
        bridge.u.GetForegroundWindow.side_effect = lambda: bridge.u.foreground
        bridge.u.IsIconic.return_value = False
        bridge.u.IsWindow.return_value = True

        def text(hwnd, buffer, length):
            buffer.value = title

        def show(hwnd, mode):
            if mode == 6:
                bridge.u.foreground = 8
            return True

        def activate(hwnd):
            if succeeds:
                bridge.u.foreground = hwnd
            return succeeds

        bridge.u.GetWindowTextW.side_effect = text
        bridge.u.ShowWindowAsync.side_effect = show
        bridge.u.SetForegroundWindow.side_effect = activate
        return bridge

    def test_library_yields_foreground_before_target_switch(self):
        bridge = self.bridge()
        bridge.activate(42)
        bridge.u.ShowWindowAsync.assert_called_once_with(7, 6)
        self.assertEqual(bridge.u.foreground, 42)
        self.assertEqual(bridge.validate.call_count, 2)
        bridge.u.AttachThreadInput.assert_not_called()

    def test_existing_target_needs_no_focus_manipulation(self):
        bridge = self.bridge()
        bridge.u.foreground = 42
        bridge.activate(42)
        bridge.u.SetForegroundWindow.assert_not_called()
        bridge.u.ShowWindowAsync.assert_not_called()

    def test_unrelated_browser_or_same_title_other_app_is_not_minimized(self):
        for title, process in [("Other Edge page", "C:/Edge/msedge.exe"), ("Plasticity 模型组件库", "C:/Other/app.exe")]:
            with self.subTest(title=title, process=process):
                bridge = self.bridge(title, process)
                bridge.activate(42)
                bridge.u.ShowWindowAsync.assert_not_called()

    def test_failure_restores_library_and_sends_no_keys(self):
        bridge = self.bridge(succeeds=False)
        with patch("windows_bridge.time.monotonic", side_effect=[0, 0, 2]), patch("windows_bridge.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "无法激活"):
                bridge.shortcut(42, "ctrl+shift+v")
        self.assertEqual(bridge.u.ShowWindowAsync.call_args_list, [unittest.mock.call(7, 6), unittest.mock.call(7, 9)])
        bridge.u.SendInput.assert_not_called()

    def test_closed_target_does_not_minimize_library(self):
        bridge = self.bridge()
        bridge.validate.side_effect = ValueError("closed")
        with self.assertRaises(ValueError):
            bridge.activate(42)
        bridge.u.ShowWindowAsync.assert_not_called()

    def test_minimized_target_is_restored(self):
        bridge = self.bridge(title="Other window")
        bridge.u.IsIconic.return_value = True
        bridge.activate(42)
        bridge.u.ShowWindowAsync.assert_called_once_with(42, 9)


if __name__ == "__main__":
    unittest.main()
