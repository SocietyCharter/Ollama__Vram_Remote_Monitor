@echo off
:: ============================================================================
:: launch.bat — Ollama Monitor Launcher
:: ----------------------------------------------------------------------------
:: SETUP:
::   1. Copy launch.bat and monitor.py to any folder (they must stay together).
::   2. Right-click launch.bat > Send To > Desktop (create shortcut).
::   3. Double-click the shortcut to launch the monitor silently.
::
:: monitor.py will appear in your system tray area / taskbar as a small window.
:: To retarget a different server, edit HOST / SSH_USER in monitor.py.
:: ============================================================================

setlocal

:: Resolve monitor.py relative to THIS .bat file (not the shortcut's location)
set "SCRIPT=%~dp0monitor.py"

if not exist "%SCRIPT%" (
    powershell -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('monitor.py not found next to launch.bat.`nMove both files to the same folder and try again.', 'Ollama Monitor', 'OK', 'Error')" >nul 2>&1
    exit /b 1
)

:: ── Try pythonw.exe from PATH first ─────────────────────────────────────────
where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    start "" pythonw.exe "%SCRIPT%"
    exit /b 0
)

:: ── Fallback: common install paths ──────────────────────────────────────────
set "CANDIDATES=C:\Python312\pythonw.exe C:\Python311\pythonw.exe C:\Python310\pythonw.exe"
set "LOCALAPP=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"

for %%P in (%CANDIDATES%) do (
    if exist "%%P" (
        start "" "%%P" "%SCRIPT%"
        exit /b 0
    )
)

if exist "%LOCALAPP%" (
    start "" "%LOCALAPP%" "%SCRIPT%"
    exit /b 0
)

:: ── No Python found ──────────────────────────────────────────────────────────
powershell -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Python 3.10+ was not found on this machine.`n`nInstall from https://www.python.org/downloads/`nMake sure to check ''Add Python to PATH'' during setup.', 'Ollama Monitor — Python Not Found', 'OK', 'Error')" >nul 2>&1
exit /b 1
