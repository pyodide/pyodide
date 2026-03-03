@echo off
setlocal ENABLEDELAYEDEXPANSION

REM VENV_DIR = Directory of this script (symlink)
REM RESOLVED_DIR = Directory of this script (resolved)
REM THIS_PROGRAM = Full path to this script (executable)
set "VENV_DIR=%~dp0"
set "RESOLVED_DIR=%~dp0"
set "THIS_PROGRAM_BATCH_FILE=%~f0"
REM replace the suffix of THIS_PROGRAM from .bat to .exe for better sys.executable compatibility
set "THIS_PROGRAM=%THIS_PROGRAM_BATCH_FILE:~0,-4%.exe"

REM Set initial arguments placeholder for the Node flags
set "NODE_ARGS="

REM Redirect python -m pip to execute in host environment
if /i "%~1"=="-m" if /i "%~2"=="pip" (
    REM Shift arguments to remove "-m pip"
    shift
    shift

    set "PIP_SCRIPT=%VENV_DIR%pip.bat"

    if not exist "%PIP_SCRIPT%" (
        >&2 echo Cannot find pyodide pip. Make a pyodide venv first?
        exit /b 1
    )

    call "%PIP_SCRIPT%" %*
    exit /b %ERRORLEVEL%
)

REM Sadly, windows doesn't seem to have realpath-equivalent built-in commands that can resolve symlinks.
REM Use 'dir /l' to get the symlink information and pipe it to findstr.
REM findstr filters the line containing the link, and FOR /F is used to parse it.
REM Note: This relies heavily on the output format being consistent.

set "TargetFullPath="
for /f "tokens=*" %%a in ('dir /l "%THIS_PROGRAM_BATCH_FILE%" ^| findstr /i /c:"SYMLINK" /c:"JUNCTION"') do (
    REM %%a contains the full line, e.g., "... <SYMLINKD> MyLink [C:\Original\Target\Folder]"

    REM --- Single-Block Parsing Logic ---
    REM 1. Use an inner FOR loop to tokenize the line using '[' as the delimiter.
    REM    The second token (%%b) will capture everything after the '[', which is "TargetFullPath]"
    set "Line=%%a"
    for /f "tokens=2 delims=[" %%b in ("!Line!") do (
        set "TargetBracketed=%%b"
    )

    REM 2. Now TargetBracketed is "C:\Original\Target\Folder]".
    REM    Strip the last character (the closing ']') using substring expansion.
    if defined TargetBracketed (
        REM The substring operation removes the last character (the ']').
        set "TargetFullPath=!TargetBracketed:~0,-1!"
    )

    goto :ProcessResult
)
REM If we reach here, it means no symlink/junction was found, probably invoking the batch file
goto :EndParse

:ProcessResult
if defined TargetFullPath (
    @REM echo Target Full Path: !TargetFullPath!

    rem Now, use another FOR loop to extract the directory path from the full path.
    rem This uses the built-in batch variable modifier '~dp' (Drive/Path)
    for %%f in ("!TargetFullPath!") do (
        set "RESOLVED_DIR=%%~dpf"
    )

) else (
    echo ERROR: Could not parse target path from 'dir /l' output.
)

:EndParse
REM Check for Node.js availability
where node >nul 2>nul
if ERRORLEVEL 1 (
    echo No node executable found on the path >&2
    exit /b 1
)

REM Determine Node Flags based on Version
(
    REM JavaScript block to check version
    echo "const major_version = Number(process.version.split('.')[0].slice(1));"
    echo "if (major_version  < 18) {"
    echo "    console.error('Need node version >= 18. Got node version', process.version);"
    echo "   process.exit(1);"
    echo "}"
    echo.
    echo "if (major_version  >= 20) {"
    echo "   process.stdout.write('--experimental-wasm-stack-switching');"
    echo "}"
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
