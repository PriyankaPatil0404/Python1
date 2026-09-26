@echo off
setlocal
if not exist .venv if not exist venv (
    python -m venv .venv
)
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    call venv\Scripts\activate.bat
)
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Setup complete. Edit .env if you want Gemini AI, then run start_windows.bat
echo.
pause
