@echo off
setlocal
cd /d "%~dp0"

rem FC27 Academy Engine launcher. The Windows release carries its own Python in runtime\python,
rem so nothing needs installing. Without it (developer copies), an installed Python is used.
if exist "%~dp0runtime\python\pythonw.exe" (
  start "FC27 Academy Engine" "%~dp0runtime\python\pythonw.exe" "%~dp0run_manager.py"
  exit /b 0
)

where py >nul 2>nul
if errorlevel 1 (
  echo This copy of FC27 Academy Engine has no built-in Python, and no Python is installed.
  echo Download the Windows release from the mod page, or install Python 3.12 from python.org.
  pause
  exit /b 1
)
py -c "import PySide6, psutil, PIL" >nul 2>nul
if errorlevel 1 (
  echo FC27 Academy Engine is installing its first-run requirements...
  py -m pip install -r requirements-gui.txt
  if errorlevel 1 (
    echo.
    echo Installation failed. Leave this window open and copy the error above for support.
    pause
    exit /b 1
  )
)

where pyw >nul 2>nul
if errorlevel 1 (
  start "FC27 Academy Engine" py run_manager.py
) else (
  start "FC27 Academy Engine" pyw run_manager.py
)
exit /b 0
