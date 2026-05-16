@echo off
cd /d %~dp0
echo NYSEO 内部リンク構築エージェントを起動しています...
pip install -r requirements.txt --quiet
streamlit run app.py
pause
