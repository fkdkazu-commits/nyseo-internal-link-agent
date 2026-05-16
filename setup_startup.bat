@echo off
echo ================================================
echo  NYSEO エージェント スタートアップ登録
echo ================================================
echo.

:: 依存パッケージのインストール
echo [1/2] 依存パッケージをインストールしています...
pip install -r requirements.txt --quiet
echo 完了
echo.

:: Windows スタートアップフォルダへ登録
echo [2/2] スタートアップへ登録しています...
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
copy /Y "%~dp0start_background.vbs" "%STARTUP%\nyseo_agent.vbs" >nul
echo 完了
echo.

echo ================================================
echo  セットアップ完了！
echo.
echo  次回からPCを起動するだけで自動的にエージェントが
echo  バックグラウンドで立ち上がります。
echo.
echo  ブラウザで以下をブックマーク登録してください：
echo  http://localhost:8501
echo.
echo  ※ 今すぐ使う場合は start.bat を実行してください
echo ================================================
pause
