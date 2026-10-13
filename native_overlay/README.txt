FC27 Academy Engine v1.0.7 external overlay

AcademyOverlayHost.exe is a separate small program built from source/academy_overlay.c (tools/build_overlay.py). It draws the overlay in its own window and never touches FC27.exe. Since v1.0.6 there is no DLL.

The renderer follows the FC27 top-level window using GAME_PID from %LOCALAPPDATA%\FC27AcademyEngine\runtime\bridge\overlay_state.txt. It reads the atomically published overlay state and writes each UI command to its own overlay_cmd_<tick>_<seq>.txt file (atomic rename), so rapid clicks are queued rather than overwritten. Files are opened with FILE_SHARE_DELETE so the engine can replace them while they are being read.

All Career Mode data access and verified writes remain in FC Live Editor's thin Lua adapter; all progression logic/persistence remains in the external Python engine.
