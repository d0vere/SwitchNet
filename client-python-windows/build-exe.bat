@echo off
setlocal
cd /d "%~dp0"

rem SwitchNet: every Windows build starts from a clean PyInstaller workspace.
if exist "%~dp0build" rmdir /s /q "%~dp0build"
if exist "%~dp0dist" rmdir /s /q "%~dp0dist"
if exist "%~dp0SwitchNetClient.spec" del /f /q "%~dp0SwitchNetClient.spec"

py -3 -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

py -3 -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name SwitchNetClient ^
  --icon "%~dp0assets\tray_active.ico" ^
  --add-data "%~dp0assets\tray_active.ico;assets" ^
  --add-data "%~dp0assets\tray_inactive.ico;assets" ^
  "%~dp0switchnet_client.py"
if errorlevel 1 goto :error

echo.
echo Build completata: %~dp0dist\SwitchNetClient.exe
echo Icona EXE: tray_active.ico
echo Le icone tray ON/OFF sono incluse nel file standalone.
pause
exit /b 0

:error
echo.
echo Build fallita.
pause
exit /b 1
