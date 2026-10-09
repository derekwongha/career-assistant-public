@echo off
title Career Assistant - Dashboard Server
cd /d "%~dp0"
echo ======================================================================
echo CAREER ASSISTANT - HUMAN REVIEW DASHBOARD
echo ======================================================================
echo.

:: 1. Verify Working Directory
if not exist "04_Application\dashboard_server.py" (
    echo [ERROR] Must be run from the CareerTransitionLocalAIAssistant root folder.
    goto FAIL
)

:: 2. Verify Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    goto FAIL
)

:: 3. Check if Dashboard Server is ALREADY running
powershell -Command "$ProgressPreference = 'SilentlyContinue'; try { $res = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/jobs' -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Dashboard server is already running on http://127.0.0.1:8080.
    echo Opening dashboard in default browser...
    start http://127.0.0.1:8080/
    goto END
)

:: 4. Start Dashboard Server in background window if not running
echo Starting Dashboard Web Server on http://127.0.0.1:8080 ...
start "Career Assistant Server" /min python 04_Application\dashboard_server.py

:: 5. Bounded polling for server health (up to 15 seconds)
echo Waiting for dashboard server to become healthy...
powershell -Command "$ProgressPreference = 'SilentlyContinue'; for ($i = 1; $i -le 15; $i++) { try { $res = Invoke-RestMethod -Uri 'http://127.0.0.1:8080/api/jobs' -TimeoutSec 2; if ($res.success) { exit 0 } } catch {}; Start-Sleep -Seconds 1 }; exit 1"
if errorlevel 1 (
    echo.
    echo ======================================================================
    echo [ERROR] Dashboard server failed to become healthy on http://127.0.0.1:8080.
    echo Please check python output or port availability.
    echo ======================================================================
    echo.
    goto FAIL
)

echo [OK] Dashboard server is healthy. Opening default browser...
start http://127.0.0.1:8080/
goto END

:FAIL
echo.
pause

:END
