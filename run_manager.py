import sys
import traceback
from pathlib import Path

_INSTANCE_MUTEX=None

def _focus_existing_launcher(ctypes,u32):
    """Bring the existing Qt launcher window forward (never the overlay, which
    shares the title but is a native popup window)."""
    from ctypes import wintypes
    found=[]
    @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def cb(hwnd,_):
        title=ctypes.create_unicode_buffer(256); cls=ctypes.create_unicode_buffer(256)
        u32.GetWindowTextW(hwnd,title,256); u32.GetClassNameW(hwnd,cls,256)
        if title.value=="FC27 Academy Engine" and cls.value.startswith("Qt"):
            found.append(hwnd); return False
        return True
    u32.EnumWindows(cb,0)
    if found:
        u32.ShowWindow(found[0],9)    # SW_RESTORE
        u32.SetForegroundWindow(found[0])

def _already_running() -> bool:
    """Allow one launcher per Windows session (v1.24.11).

    A second launcher would start a second bridge/overlay against the same files.
    If one is already open, bring its window to the front and exit quietly.
    """
    global _INSTANCE_MUTEX
    try:
        import ctypes
        k32=ctypes.WinDLL("kernel32",use_last_error=True); u32=ctypes.WinDLL("user32",use_last_error=True)
        k32.CreateMutexW.restype=ctypes.c_void_p
        _INSTANCE_MUTEX=k32.CreateMutexW(None,False,"Local\\FC27AcademyEngineLauncher")
        if ctypes.get_last_error()!=183:   # ERROR_ALREADY_EXISTS
            return False
        try: _focus_existing_launcher(ctypes,u32)
        except Exception: pass
        return True
    except Exception:
        return False   # non-Windows / no ctypes: never block startup


def _wait_for_previous_launcher() -> None:
    """v1.0.1: a launcher restarted as administrator waits for the old one to close first,
    otherwise the single-instance check would hand control back to the old window."""
    if "--wait-for-pid" not in sys.argv:
        return
    try:
        pid = int(sys.argv[sys.argv.index("--wait-for-pid") + 1])
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from academy_manager.elevation import wait_for_pid
        wait_for_pid(pid, timeout=20.0)
    except Exception:
        pass


_wait_for_previous_launcher()
if _already_running():
    raise SystemExit(0)

try:
    from academy_manager.main import run
    raise SystemExit(run())
except SystemExit:
    raise
except Exception:
    message = traceback.format_exc()
    try:
        (Path(__file__).resolve().parent / "startup_error.log").write_text(message, encoding="utf-8")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "FC27 Academy Engine could not start.\n\nA startup_error.log file has been created beside the launcher.\n\n" + message[-1800:], "FC27 Academy Engine - Startup Error", 0x10)
    except Exception:
        pass
    raise
