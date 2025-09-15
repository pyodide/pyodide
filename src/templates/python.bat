@echo off
setlocal enabledelayedexpansion

REM Check if first two arguments are "-m" and "pip"
if "%1"=="-m" (
    if "%2"=="pip" (
        REM Shift arguments by removing first two
        shift
        shift

        REM Check if pip exists in the same directory as this script
        set "PIP_FOUND=0"
        if exist "%~dp0pip.exe" (
            set "PIP_FOUND=1"
            set "PIP_CMD=%~dp0pip.exe"
        ) else if exist "%~dp0pip.bat" (
            set "PIP_FOUND=1"
            set "PIP_CMD=%~dp0pip.bat"
        ) else if exist "%~dp0pip.cmd" (
            set "PIP_FOUND=1"
            set "PIP_CMD=%~dp0pip.cmd"
        ) else if exist "%~dp0pip" (
            REM Try to execute pip as a Python script
            set "PIP_FOUND=1"
            set "PIP_CMD=python "%~dp0pip""
        )

        if "!PIP_FOUND!"=="0" (
            echo Cannot find pyodide pip. Make a pyodide venv first? >&2
            exit /b 1
        )

        REM Execute pip with remaining arguments
        !PIP_CMD! %*
        exit /b %errorlevel%
    )
)

REM Check if node is available
where node >nul 2>&1
if errorlevel 1 (
    echo No node executable found on the path >&2
    exit /b 1
)

REM Create temporary file for node script
set "TEMP_JS=%TEMP%\node_version_check_%RANDOM%.js"

REM Write node script to temporary file
(
echo "const major_version = Number(process.version.split('.')[0].slice(1));"
echo "if (major_version  < 18) {"
echo "    console.error('Need node version >= 18. Got node version', process.version);"
echo "   process.exit(1);"
echo "}"
echo.
echo "if (major_version  >= 20) {"
echo "   process.stdout.write('--experimental-wasm-stack-switching');"
echo "}"
) > "%TEMP_JS%"


REM Execute node script and capture output
for /f "delims=" %%i in ('node "%TEMP_JS%" 2^>nul') do set "ARGS=%%i"

REM Clean up temporary file
del "%TEMP_JS%" >nul 2>&1

REM Check if node script failed (ARGS will be empty if it failed)
if errorlevel 1 (
    node "%TEMP_JS%"
    exit /b %errorlevel%
)

REM Get the directory where this script is located
set "RESOLVED_DIR=%~dp0"
REM Remove trailing backslash
if "%RESOLVED_DIR:~-1%"=="\" set "RESOLVED_DIR=%RESOLVED_DIR:~0,-1%"

REM Get the full path of this script
set "THIS_PROGRAM=%~f0"

REM Execute the main node script with arguments
node %NODEFLAGS% %ARGS% "%RESOLVED_DIR%\python_cli_entry.mjs" --this-program="%THIS_PROGRAM%" %*
