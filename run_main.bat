@echo off
setlocal DisableDelayedExpansion

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
    exit /b 1
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
    exit /b 1
)

set "BACKEND_DIR=Memento-Mori-Site\backend"
set "BACKEND_PORT=3001"

if not exist "%BACKEND_DIR%\package.json" (
    echo Backend directory not found at %BACKEND_DIR%.
    exit /b 1
)

echo Preparing backend server dependencies...
pushd "%BACKEND_DIR%"
call "%NPM_CMD%" install --no-fund --no-audit
if errorlevel 1 (
    echo Failed to install backend dependencies.
    popd
    exit /b 1
)

echo Building backend server...
call "%NPM_CMD%" run build
if errorlevel 1 (
    echo Failed to build backend server.
    popd
    exit /b 1
)
popd

:: Start the backend server if it is not already listening
powershell -NoProfile -Command "if ((Test-NetConnection -ComputerName 'localhost' -Port %BACKEND_PORT% -WarningAction SilentlyContinue).TcpTestSucceeded) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo Starting backend server on port %BACKEND_PORT% ...
    start "Memento Mori Backend" cmd /c "cd /d ^\"%BACKEND_DIR%^\" ^&^& ^\"%NPM_CMD%^\" run start"
    timeout /t 5 >nul
) else (
    echo Backend server already running on port %BACKEND_PORT%.
)

set "VENV_DIR=.venv"

:: Create the virtual environment if it does not exist
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating virtual environment in %VENV_DIR% ...
    "%PY_CMD%" -m venv "%VENV_DIR%"
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
    exit /b 1
)

:: Run the main application
"%VENV_DIR%\Scripts\python.exe" main.py %*
exit /b %errorlevel%
