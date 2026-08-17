@echo off
setlocal enabledelayedexpansion

echo =================================================================
echo   NASA C-MAPSS Aircraft Engine Health Monitoring ^& Advisory
echo =================================================================
echo.

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

if "%~1"=="" (
    set "CMD_DATASET=FD001"
) else (
    set "CMD_DATASET=%~1"
)

echo [1/4] Running Data Engineering Pipeline (%CMD_DATASET%)...
py run_pipeline.py --dataset %CMD_DATASET%
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Data engineering pipeline failed.
    exit /b %ERRORLEVEL%
)
echo.

echo [2/4] Training RUL Prediction Models (%CMD_DATASET%)...
py train_rul_models.py --dataset %CMD_DATASET% --model both
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] RUL model training failed.
    exit /b %ERRORLEVEL%
)
echo.

echo [3/4] Running Anomaly Detection Pipeline (%CMD_DATASET%)...
py run_anomaly_detection.py --dataset %CMD_DATASET%
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Anomaly detection pipeline failed.
    exit /b %ERRORLEVEL%
)
echo.

echo [4/4] Generating Fleet Health Advisory & Launching Dashboard Server...
py run_maintenance_advisor.py --dataset %CMD_DATASET% --serve --port 8000
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Maintenance advisor execution failed.
    exit /b %ERRORLEVEL%
)

endlocal
