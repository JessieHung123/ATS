@echo off
cd /d "%~dp0"
title ATS 職能評分教學系統

netstat -ano | findstr /r /c:"127.0.0.1:8765 .*LISTENING" >nul
if not errorlevel 1 (
    echo 系統已經在執行中，直接開啟瀏覽器：http://127.0.0.1:8765
    echo 若要重新啟動，請先關閉原本的黑色視窗，或在 VS Code 按紅色方塊停止偵錯。
    start http://127.0.0.1:8765
    timeout /t 5 >nul
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    echo [首次執行] 建立 Python 環境並安裝套件，約需 1-3 分鐘...
    python -m venv .venv
    if errorlevel 1 (
        echo 找不到 Python，請先安裝 Python 3.11 以上版本：https://www.python.org/downloads/
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo 套件安裝失敗，請檢查網路連線後再試一次。
        pause
        exit /b 1
    )
)

echo.
echo 系統啟動中，瀏覽器會自動打開 http://127.0.0.1:8765
echo 使用期間請不要關閉這個視窗；要停止系統，直接關掉這個視窗即可。
echo.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8765
pause
