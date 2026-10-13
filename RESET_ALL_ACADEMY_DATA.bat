@echo off
setlocal
cls
echo FC27 Academy Engine v1.0.6 - Factory Reset
echo.
echo This deletes ALL Academy Engine state under:
echo   %%LOCALAPPDATA%%\FC27AcademyEngine
echo.
echo Close FC27, FC Live Editor and Academy Engine first.
echo.
set /p CONFIRM=Type DELETE to continue: 
if /I not "%CONFIRM%"=="DELETE" goto :cancel
if defined LOCALAPPDATA rmdir /s /q "%LOCALAPPDATA%\FC27AcademyEngine" 2>nul
echo.
echo Academy Engine state cleared.
pause
exit /b 0
:cancel
echo Cancelled.
pause
exit /b 1
