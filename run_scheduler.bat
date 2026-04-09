@echo off
:: SmartFlow Continuous Collection Scheduler
:: Starts APScheduler and runs all collectors on their poll intervals
:: Check status: scheduler_status.bat
title SmartFlow Scheduler
cd /d C:\Users\user\SmartFlow
echo SmartFlow scheduler starting...
py -3 -m smartflow schedule --all
