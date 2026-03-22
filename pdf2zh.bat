@echo off
setlocal

set "APP_DIR=%~dp0"
set "PYTHONW=%APP_DIR%core\runtime\pythonw.exe"
set "SCRIPT=%APP_DIR%_launcher.py"

:: Check Python exists
if not exist "%PYTHONW%" (
    echo [pdf2zh] Python not found: %PYTHONW%
    echo Please run install.bat first.
    pause
    exit /b 1
)

:: Check VC++ Redistributable (needed for AI layout detection)
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Version >nul 2>&1
if errorlevel 1 (
    if exist "%APP_DIR%VC_redist.x64.exe" (
        echo.
        echo Visual C++ Redistributable not installed.
        echo It is needed for AI layout detection.
        echo.
        choice /C YN /M "Install it now? (requires admin rights)"
        if not errorlevel 2 (
            echo Installing VC++ Redistributable...
            "%APP_DIR%VC_redist.x64.exe" /install /passive /norestart
        )
    )
)

:: Clear Python environment to avoid conflicts
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONIOENCODING=utf-8"

:: Launch GUI (pythonw.exe = no console window)
start "" "%PYTHONW%" "%SCRIPT%"
