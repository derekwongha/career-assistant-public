@echo off
title Career Assistant - Run Daily Job Batch
cd /d "%~dp0"
echo ======================================================================
echo CAREER ASSISTANT - DAILY JOB BATCH
echo ======================================================================
echo.

:: 1. Verify Working Directory
if not exist "04_Application\daily_job_batch.py" (
    echo [ERROR] Must be run from the CareerTransitionLocalAIAssistant root folder.
    echo Current Directory: %CD%
    goto FAIL
)

:: 2. Verify Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH. Please install Python 3.11+.
    goto FAIL
)

:: 3. Check LM Studio API & Loaded Model Availability
echo Checking LM Studio API at http://127.0.0.1:1234/v1/models ...
python 04_Application\check_lm_studio.py
if errorlevel 1 goto LMSTUDIO_FAIL
goto LMSTUDIO_OK

:LMSTUDIO_FAIL
echo.
echo ======================================================================
echo [WARNING] LM Studio API or required model is unavailable at http://127.0.0.1:1234
echo ======================================================================
echo Please:
echo 1. Open LM Studio
echo 2. Load openai/gpt-oss-20b ^(Context: 16384, reasoning_effort: medium^)
echo 3. Start the local API server ^(Port 1234^)
echo 4. Run this launcher again
echo ======================================================================
echo.
goto FAIL

:LMSTUDIO_OK

echo [OK] LM Studio API is active and model openai/gpt-oss-20b is loaded.
echo Starting Daily Job Batch (Acquisition + Deduplication + Analysis)...
echo.

:: 4. Run Daily Job Batch
python 04_Application\daily_job_batch.py --analyse
if errorlevel 1 goto FAIL

echo.
echo ======================================================================
echo [SUCCESS] Daily job batch completed successfully.
echo ======================================================================
goto END

:FAIL
echo.
echo ======================================================================
echo [FAILURE] Daily job batch did not complete cleanly.
echo ======================================================================

:END
echo.
pause
