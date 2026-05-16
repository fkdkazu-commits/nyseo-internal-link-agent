@echo off
chcp 65001 >nul
cd /d %~dp0

echo ================================================
echo  NYSEO Internal Link Agent - Setup
echo ================================================
echo.

echo [1/2] Installing packages...
pip install -r requirements.txt --quiet
echo Done.
echo.

echo [2/2] Registering startup...
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
copy /Y "%~dp0start_background.vbs" "%STARTUP%\nyseo_agent.vbs" >nul
echo Done.
echo.

echo ================================================
echo  Setup complete!
echo.
echo  The agent will start automatically on next boot.
echo  Bookmark this URL in your browser:
echo  http://localhost:8501
echo.
echo  To start now, run start.bat
echo ================================================
pause
