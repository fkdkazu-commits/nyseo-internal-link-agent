@echo off
chcp 65001 >nul
cd /d %~dp0
echo Starting NYSEO Internal Link Agent...
pip install -r requirements.txt --quiet
python -m streamlit run app.py
pause
