from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "client-python-windows" / "keyboard_mouse_backend.py").read_text(encoding="utf-8")


def test_raw_input_window_class_is_restart_safe():
    assert "self._generation += 1" in SRC
    assert 'class_name=f"{self._window_class_prefix}_{generation}"' in SRC
    assert "UnregisterClassW" in SRC
    assert "RIDEV_REMOVE" in SRC
    assert "self.user32.DestroyWindow(hwnd)" in SRC


def test_native_callback_lifetime_is_protected():
    assert "self._retired_callbacks=[]" in SRC
    assert "if not class_unregistered:" in SRC
    assert "self._retired_callbacks.append" in SRC
    assert "self._kbd_cb=kbd" in SRC
    assert "self._mouse_cb=mouse_hook" in SRC
    assert "self._wndproc=wndproc" in SRC


def test_message_loop_uses_real_win32_msg_structure():
    assert "msg=wintypes.MSG()" in SRC
    assert "PostThreadMessageW(thread_id,WM_QUIT,0,0)" in SRC


def test_hook_install_failures_are_explicit():
    assert "SetWindowsHookExW failed for keyboard hook" in SRC
    assert "SetWindowsHookExW failed for mouse hook" in SRC
    assert "RegisterRawInputDevices failed for Keyboard+Mouse" in SRC
