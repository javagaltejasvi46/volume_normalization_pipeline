@echo off
setlocal
title Batch Audio Leveler
cd /d "%~dp0"

REM Check for virtual environments
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

REM Launch Batch Audio Leveler passing all command-line arguments (if any)
python -m batch_audio_leveler %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo Application exited with code %ERRORLEVEL%.
    pause
)

endlocal
