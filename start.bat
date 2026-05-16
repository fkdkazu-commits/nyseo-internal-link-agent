@echo off
chcp 65001 >nul
cd /d %~dp0
echo Starting NYSEO Internal Link Agent...
pip install -r requirements.txt --quiet

:: py ランチャー優先、なければ pip と同じ Python を使用
where py >nul 2>&1
if %errorlevel%==0 (
    py -m streamlit run app.py
    goto end
)

:: py がない場合、pip の場所から Python を特定して起動
for /f "tokens=*" %%i in ('where pip 2^>nul') do set PIP_EXE=%%i
if defined PIP_EXE (
    for %%i in ("%PIP_EXE%") do set PYTHON_EXE=%%~dpi..\python.exe
    "%PYTHON_EXE%" -m streamlit run app.py
    goto end
)

echo ERROR: Python not found. Please check your Python installation.
:end
pause
