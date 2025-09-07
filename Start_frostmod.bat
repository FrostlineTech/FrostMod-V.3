@echo off

REM FrostMod launcher (Windows)
REM - Sets UTF-8 code page
REM - Sets blue text on black background
REM - Sets console title

chcp 65001 >nul
color 01
title "FrostMod - Discord Moderation Bot"

echo Starting FrostMod...
echo Press Ctrl+C followed by Y to shut down

REM Set environment variable to trigger export on shutdown
set FROSTMOD_EXPORT_ON_EXIT=true

REM Run with Python's unbuffered mode (-u) for real-time logs
python -u frostmodv3.py

echo.
echo Bot has shut down.
echo Check user_data directory for exported files.
echo.
echo Press any key to exit...
pause > nul
