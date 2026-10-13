"""Run Academy Engine at the same level as FC27 (v1.0.1).

When Live Editor starts FC27 as administrator and Academy Engine runs normally, Windows
blocks the overlay from taking focus over the game and blocks reading the game process.
The fix is to run Academy Engine as administrator too: the launcher restarts itself through
the normal Windows UAC prompt, and the new (elevated) launcher waits for the old one to close
before it takes over. Academy Engine never needs administrator rights for anything else.
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SE_ERR_ACCESSDENIED = 5          # ShellExecute: the user said No at the UAC prompt


def is_elevated() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def gui_python() -> str:
    """pythonw.exe for the restarted launcher (no console window), else the current interpreter."""
    exe = Path(sys.executable)
    if exe.name.lower() == "python.exe" and (exe.parent / "pythonw.exe").exists():
        return str(exe.parent / "pythonw.exe")
    return str(exe)


def restart_command(pid: int) -> tuple[str, str, str]:
    """(program, parameters, working folder) for the elevated restart."""
    return gui_python(), f'"{ROOT / "run_manager.py"}" --wait-for-pid {int(pid)}', str(ROOT)


def relaunch_elevated(pid: int | None = None, shell_execute=None) -> tuple[bool, str]:
    """Start a new launcher as administrator (UAC prompt). Returns (started, message)."""
    pid = os.getpid() if pid is None else pid
    program, params, folder = restart_command(pid)
    try:
        if shell_execute is None:
            import ctypes
            shell_execute = ctypes.windll.shell32.ShellExecuteW
        rc = int(shell_execute(None, "runas", program, params, folder, 1))
    except Exception as exc:
        return False, f"Could not restart as administrator: {exc}"
    if rc > 32:
        return True, "Restarting Academy Engine as administrator…"
    if rc == SE_ERR_ACCESSDENIED:
        return False, "Administrator permission was not given, so Academy Engine was not restarted."
    return False, f"Could not restart as administrator (Windows error {rc})."


def wait_for_pid(pid: int, timeout: float = 20.0) -> bool:
    """Wait for a process to end. True if it ended (or never existed) within the timeout."""
    try:
        import psutil
        try:
            psutil.Process(int(pid)).wait(timeout=timeout)
        except psutil.NoSuchProcess:
            pass
        return True
    except ImportError:
        pass
    except Exception:
        return False
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            os.kill(int(pid), 0)
        except OSError:
            return True
        time.sleep(0.2)
    return False
