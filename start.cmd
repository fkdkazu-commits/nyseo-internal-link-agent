@echo off
chcp 65001 >nul
cd /d %~dp0
echo Starting NYSEO Internal Link Agent...
pip install -r requirements.txt --quiet

where py >nul 2>&1
if %errorlevel%==0 (
    py -m streamlit run app.py --server.headless true
    goto end
)

for /f "tokens=*" %%i in ('where pip 2^>nul') do set PIP_EXE=%%i
if defined PIP_EXE (
    for %%i in ("%PIP_EXE%") do set PYTHON_EXE=%%~dpi..\python.exe
    "%PYTHON_EXE%" -m streamlit run app.py --server.headless true
    goto end
)

echo ERROR: Python not found. Please check your Python installation.
:end
pause
