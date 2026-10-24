@echo off
setlocal EnableDelayedExpansion
title Git Sync - Pull Latest ^& Push to Main
cd /d "%~dp0"

echo ========================================================
echo         Volume Normalization Pipeline - Git Sync
echo ========================================================
echo.

REM Check if git is available
where git >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Git is not installed or not found in system PATH.
    pause
    exit /b 1
)

REM Step 1: Stage all local changes
echo [1/4] Staging local changes...
git add -A

REM Step 2: Commit if there are changes
echo [2/4] Checking for local changes to commit...
git diff-index --quiet HEAD -- >nul 2>&1
if %ERRORLEVEL% neq 0 (
    set "RAW_MSG=%*"
    if not defined RAW_MSG (
        set /p "RAW_MSG=Enter commit message (press Enter for default): "
    )
    if not defined RAW_MSG (
        set "RAW_MSG=Update: %date% %time%"
    )
    REM Strip double quotes to prevent syntax errors
    set "CLEAN_MSG=!RAW_MSG:"=!"
    if "!CLEAN_MSG!"=="" (
        set "CLEAN_MSG=Update: %date% %time%"
    )
    echo Committing changes with message: "!CLEAN_MSG!"
    git commit -m "!CLEAN_MSG!"
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to commit changes.
        pause
        exit /b !ERRORLEVEL!
    )
) else (
    echo Working tree clean. No new local changes to commit.
)

REM Step 3: Pull latest changes from origin main
echo.
echo [3/4] Pulling latest changes from origin main...
git pull --rebase origin main
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Git pull failed. Please check your internet connection or resolve merge conflicts.
    pause
    exit /b %ERRORLEVEL%
)

REM Step 4: Push to origin main
echo.
echo [4/4] Pushing all commits to origin main...
git push origin main
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Git push failed. Please check your permissions or network connection.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================================
echo [SUCCESS] Local repo updated and pushed to origin main!
echo ========================================================
echo.
if "%~1"=="" pause
endlocal
