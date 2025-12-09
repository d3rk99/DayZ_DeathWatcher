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
set "BACKEND_DIR=Memento-Mori-Site\backend"

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

:: Start the backend dev server if npm is available
set "NPM_CMD="
for %%N in (npm.cmd npm.exe npm) do (
    where %%N >nul 2>&1
    if not errorlevel 1 (
        set "NPM_CMD=%%N"
        goto :found_npm
    )
)

:found_npm
if not "!NPM_CMD!"=="" (
    if exist "%BACKEND_DIR%" (
        pushd "%BACKEND_DIR%"
        if not exist "node_modules" (
            echo Installing backend dependencies in %BACKEND_DIR% ...
            "!NPM_CMD!" install
            if errorlevel 1 (
                echo Failed to install backend dependencies.
                popd
                exit /b 1
            )
        )
        echo Starting backend dev server with npm run dev ...
        start "Memento Mori Backend" "!NPM_CMD!" run dev
        popd
    ) else (
        echo Backend directory not found: %BACKEND_DIR%
    )
) else (
    echo npm was not found on PATH; skipping backend dev server startup.
)

:: Install dependencies
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    exit /b 1
)

:: Run the main application
"%VENV_DIR%\Scripts\python.exe" main.py %*
exit /b %errorlevel%
