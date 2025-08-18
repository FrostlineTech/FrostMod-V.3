@echo off
REM FrostMod launcher (Windows)
REM - Sets UTF-8 code page
REM - Sets blue text on black background
REM - Sets console title

chcp 65001 >nul
color 01
title "FrostMod - Discord Moderation Bot"

REM Unbuffered Python (-u) for real-time logs
python -u frostmodv3.py

pause
