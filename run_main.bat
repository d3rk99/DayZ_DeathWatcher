@echo off
setlocal DisableDelayedExpansion

set "EXIT_CODE=0"

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
if "%PY_CMD%"=="" (
    echo Python is not installed or not available on PATH.
    set "EXIT_CODE=1"
    goto :finish
)

echo Using Python command: %PY_CMD%

:: Locate npm for the website backend
set "NPM_CMD="
for /f "delims=" %%N in ('where npm.cmd 2^>nul') do (
    if not defined NPM_CMD set "NPM_CMD=%%~fN"
)
if not defined NPM_CMD for /f "delims=" %%N in ('where npm.exe 2^>nul') do (
    if not defined NPM_CMD set "NPM_CMD=%%~fN"
)
if not defined NPM_CMD for /f "delims=" %%N in ('where npm 2^>nul') do (
    if not defined NPM_CMD set "NPM_CMD=%%~fN"
)

:found_npm
if "%NPM_CMD%"=="" (
    echo Node.js and npm are required to run the backend API but were not found on PATH.
    set "EXIT_CODE=1"
    goto :finish
)

set "BACKEND_DIR=Memento-Mori-Site\backend"
set "BACKEND_PORT=3001"

:: Resolve absolute backend paths to avoid issues with spaces or special characters
for %%I in ("%BACKEND_DIR%") do set "BACKEND_DIR=%%~fI"

if not exist "%BACKEND_DIR%\package.json" (
    echo Backend directory not found at %BACKEND_DIR%.
    set "EXIT_CODE=1"
    goto :finish
)

echo Preparing backend server dependencies...
pushd "%BACKEND_DIR%"
call "%NPM_CMD%" install --no-fund --no-audit
if errorlevel 1 (
    echo Failed to install backend dependencies.
    popd
    set "EXIT_CODE=1"
    goto :finish
)
popd

:: Start the backend server in dev mode if it is not already listening
powershell -NoProfile -Command "\$ErrorActionPreference='SilentlyContinue'; if (Test-NetConnection -ComputerName 'localhost' -Port %BACKEND_PORT% -InformationLevel Quiet) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo Starting backend server (npm run dev) on port %BACKEND_PORT% ...
    echo A backend window will stay open so any crash output is visible.
    set "BACKEND_RUN=cd /d \"%BACKEND_DIR%\" && \"%NPM_CMD%\" run dev ^& echo. ^& echo Backend process exited. Press any key to review the output. ^& pause"
    start "Memento Mori Backend" cmd /k "%BACKEND_RUN%"
    for /l %%I in (1,1,12) do (
        powershell -NoProfile -Command "\$ErrorActionPreference='SilentlyContinue'; if (Test-NetConnection -ComputerName 'localhost' -Port %BACKEND_PORT% -InformationLevel Quiet) { exit 0 } else { exit 1 }" >nul 2>&1
        if not errorlevel 1 goto :backend_ready
        timeout /t 1 >nul
    )
    echo Backend server failed to start. Check the backend window for error details.
    set "EXIT_CODE=1"
    goto :finish
) else (
    echo Backend server already running on port %BACKEND_PORT%.
)

:backend_ready

set "VENV_DIR=.venv"

:: Create the virtual environment if it does not exist
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment in %VENV_DIR% ...
    "%PY_CMD%" -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        set "EXIT_CODE=1"
        goto :finish
    )
)

:: Activate the virtual environment
call "%VENV_DIR%\Scripts\activate"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    set "EXIT_CODE=1"
    goto :finish
)

:: Install dependencies
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    set "EXIT_CODE=1"
    goto :finish
)

:: Run the main application
"%VENV_DIR%\Scripts\python.exe" main.py %*
set "EXIT_CODE=%errorlevel%"

:finish
if not "%EXIT_CODE%"=="0" (
    echo Launcher finished with exit code %EXIT_CODE%.
    echo Press any key to close this window after reviewing the messages above.
    pause >nul
)
exit /b %EXIT_CODE%
