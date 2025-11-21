@echo off
setlocal

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "ACTIVATE_BAT=%VENV_DIR%\Scripts\activate.bat"

if not exist "%PYTHON_EXE%" (
    echo [INFO] No virtual environment found at %VENV_DIR%. Creating one with Python 3.11 if available...
    where py >nul 2>&1
    if %errorlevel%==0 (
        py -3.11 -m venv "%VENV_DIR%" || py -3 -m venv "%VENV_DIR%"
    ) else (
        python -m venv "%VENV_DIR%"
    )
)

if not exist "%ACTIVATE_BAT%" (
    echo [ERROR] Unable to create or locate a virtual environment in %VENV_DIR%. >&2
    exit /b 1
)

call "%ACTIVATE_BAT%"

python -m pip install --upgrade pip || goto :error
pip install -r requirements.txt || goto :error

python main.py

exit /b 0

:error
echo [ERROR] Setup or runtime failed. >&2
exit /b 1
