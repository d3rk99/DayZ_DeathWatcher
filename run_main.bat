@echo off
setlocal enabledelayedexpansion

:: Change to the directory of this script
cd /d "%~dp0"

:: Locate a Python interpreter
set "PY_CMD="
for %%P in (python.exe python) do (
    where %%P >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=%%P"
        goto :found_python
    )
)
where py >nul 2>&1
if not errorlevel 1 set "PY_CMD=py"

:found_python
if "!PY_CMD!"=="" (
    echo Python is not installed or not available on PATH.
    exit /b 1
)

echo Using Python command: !PY_CMD!

set "VENV_DIR=.venv"

:: Create the virtual environment if it does not exist
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment in %VENV_DIR% ...
    "!PY_CMD!" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
)

:: Activate the virtual environment
call "%VENV_DIR%\Scripts\activate"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    exit /b 1
)

:: Install dependencies
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

:: Run the main application
"%VENV_DIR%\Scripts\python.exe" main.py %*
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo The application exited with error code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%
