@echo off
py -3 "%~dp0switchnet_client.py"
if errorlevel 1 pause
