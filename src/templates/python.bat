@echo off
setlocal enabledelayedexpansion

REM Handle python -m pip redirection
IF "%1"=="-m" (
    IF "%2"=="pip" (
        shift
        shift
        IF NOT EXIST "%~dp0pip" (
            echo Cannot find pyodide pip. Make a pyodide venv first? 1>&2
            exit /b 1
        )
        "%~dp0pip" %*
        exit /b %ERRORLEVEL%
    )
)

REM Check for node
where node >nul 2>nul
IF ERRORLEVEL 1 (
    echo No node executable found on the path 1>&2
    exit /b 1
)

REM Get Node.js version and compute ARGS
FOR /F "usebackq tokens=* delims=" %%A IN (`node -e "const v = process.version.split('.')[0].slice(1); if(+v < 18){ console.error('Need node version >= 18. Got node version', process.version); process.exit(1); } if(+v >= 20){ process.stdout.write('--experimental-wasm-stack-switching'); }"`) DO (
    set "ARGS=%%A"
)

REM Resolve this script's directory
set "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash if exists
IF "%SCRIPT_DIR:~-1%"=="\" SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

REM Get full path to this script (non-symlink)
set "THIS_PROGRAM=%~f0"

REM Run the Node.js entry point with flags
node %NODEFLAGS% %ARGS% "%SCRIPT_DIR%\python_cli_entry.mjs" --this-program="%THIS_PROGRAM%" %*
