@echo off
:: SmartFlow Scheduler Status Check
:: Usage: Double-click to see if scheduler is running

cd /d C:\Users\user\SmartFlow

echo Checking SmartFlow scheduler status...
echo.

:: Check if python process with smartflow is running
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE 2>nul | findstr /i "smartflow" >nul
if %errorlevel%==0 (
    echo [RUNNING] SmartFlow scheduler is active
    echo.
    echo Recent log entries:
    powershell -Command "Get-Content 'C:\Users\user\SmartFlow\logs\smartflow.log' -Tail 10 -ErrorAction SilentlyContinue"
) else (
    echo [STOPPED] SmartFlow scheduler is not running
    echo.
    echo To start: run run_scheduler.bat
)

echo.
echo DB status:
py -3 -c "from smartflow.db.engine import get_session, init_db; from smartflow.db.models import SmartMoneySignal, CollectionRun; init_db(); s = get_session(); total = s.query(SmartMoneySignal).count(); last_run = s.query(CollectionRun).order_by(CollectionRun.started_at.desc()).first(); print(f'Signals: {total}'); print(f'Last run: {last_run.started_at.strftime(\"%m-%d %H:%M\")} - {last_run.collector} ({last_run.status})') if last_run else print('No runs'); s.close()"

echo.
pause
