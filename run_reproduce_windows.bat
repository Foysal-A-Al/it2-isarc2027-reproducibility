@echo off
setlocal
cd /d "%~dp0"
call conda activate it2
if errorlevel 1 exit /b 1
set "IT2_MODE=%~1"
if not defined IT2_MODE set "IT2_MODE=saved-features"
python scripts\reproduce_study.py --mode "%IT2_MODE%"
exit /b %errorlevel%
