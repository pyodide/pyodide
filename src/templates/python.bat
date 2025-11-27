@echo off
setlocal ENABLEDELAYEDEXPANSION

REM RESOLVED_DIR = Directory of this script
REM THIS_PROGRAM = Full path to this script
set "RESOLVED_DIR=%~dp0"
set "THIS_PROGRAM=%~f0"

REM Set initial arguments placeholder for the Node flags
set "NODE_ARGS="

REM Redirect python -m pip to execute in host environment
if /i "%1"=="-m" if /i "%2"=="pip" (
    REM Shift arguments to remove "-m pip"
    shift
    shift
    
    set "PIP_SCRIPT=%RESOLVED_DIR%pip"

    if not exist "%PIP_SCRIPT%" (
        >&2 echo Cannot find pyodide pip. Make a pyodide venv first?
        exit /b 1
    )

    call "%PIP_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

REM Check for Node.js availability
where node >nul 2>nul
if ERRORLEVEL 1 (
    echo No node executable found on the path >&2 
    exit /b 1
)

REM Determine Node Flags based on Version
(
    REM JavaScript block to check version
    echo const major_version = Number(process.version.split(".")[0].slice(1));
    echo if(major_version ^< 18) {
    echo     console.error("Need node version ^>= 18. Got node version", process.version);
    echo     process.exit(1);
    echo }
    echo if (major_version ^>= 20) {
    echo     process.stdout.write("--experimental-wasm-stack-switching");
    echo }
)> "%TEMP%\__node_check.js"

REM Run Node.js and capture the output (the dynamic argument) into NODE_ARGS
REM The use of 'FOR /F' captures stdout.
FOR /F "delims=" %%i IN ('node "%TEMP%\__node_check.js"') DO (
    set "NODE_ARGS=%%i"
)

del "%TEMP%\__node_check.js" 2>nul
    
if ERRORLEVEL 1 (
    echo Node.js version check failed or exited with error. >&2
    exit /b 1
)

REM Compute our own path, not following symlinks and pass it in so that
REM node_entry.mjs can set sys.executable correctly.
REM Intentionally allow word splitting on %NODEFLAGS%.
call node %NODEFLAGS% !NODE_ARGS! "%RESOLVED_DIR%python_cli_entry.mjs" --this-program="%THIS_PROGRAM%" %*

exit /b %ERRORLEVEL%