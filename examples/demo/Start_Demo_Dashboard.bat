@echo off
title DEMO Dashboard (synthetic data)
cd /d "%~dp0\..\.."
python examples\demo\make_demo.py
if errorlevel 1 goto FAIL
start "" http://127.0.0.1:8081/
python examples\demo\run_demo.py
goto END
:FAIL
echo [ERROR] Could not build the synthetic demo data.
:END
pause
