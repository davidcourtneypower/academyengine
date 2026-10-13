@echo off
setlocal
cd /d "%~dp0"
rem Removes Academy Engine from Live Editor and, if you confirm, deletes its data.
rem Your FC27 saves are never touched. Delete this folder afterwards.
if exist "%~dp0runtime\python\python.exe" (
  "%~dp0runtime\python\python.exe" "%~dp0academy_manager\uninstall.py"
) else (
  py "%~dp0academy_manager\uninstall.py"
)
pause
