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

REM Redirect python -m pip to execute in host environment.
REM Not a parenthesised block: cmd parses those in one pass, so %PIP_SCRIPT%
REM would read back empty and shift would not move the %1 references.
if /i not "%~1"=="-m" goto :NotPip
if /i not "%~2"=="pip" goto :NotPip

set "PIP_SCRIPT=%VENV_DIR%pip.bat"

if not exist "%PIP_SCRIPT%" (
    >&2 echo Cannot find pyodide pip. Make a pyodide venv first?
    exit /b 1
)

REM Leave delayed expansion before touching the arguments, it eats any "!".
endlocal & set "PIP_SCRIPT=%PIP_SCRIPT%"

REM Drop the "-m pip" prefix. shift does not touch %*, so rebuild the rest.
shift
shift
set "PIP_ARGS="

:CollectPipArgs
if "%~1"=="" if [%1]==[] goto :RunPip
set "PIP_ARGS=%PIP_ARGS% "%~1""
shift
goto :CollectPipArgs

:RunPip
call "%PIP_SCRIPT%"%PIP_ARGS%
exit /b %ERRORLEVEL%

:NotPip

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

REM Determine Node Flags based on Version.
REM %TEMP% is not guaranteed to be set, so fall back to %TMP% then here.
set "NODE_CHECK_DIR=%TEMP%"
if not defined NODE_CHECK_DIR set "NODE_CHECK_DIR=%TMP%"
if not defined NODE_CHECK_DIR set "NODE_CHECK_DIR=%~dp0."

REM %RANDOM% in the name so concurrent invocations do not clobber each other.
set "NODE_CHECK_JS=%NODE_CHECK_DIR%\__pyodide_node_check_%RANDOM%%RANDOM%.js"
set "NODE_CHECK_OUT=%NODE_CHECK_JS%.out"
(
    REM JavaScript block to check version
    echo "const major_version = Number(process.version.split('.')[0].slice(1));"
    echo "if (major_version  < 18) {"
    echo "    console.error('Need node version >= 18. Got node version', process.version);"
    echo "   process.exit(1);"
    echo "}"
    echo.
    echo "if (major_version  >= 20 ^&^& major_version ^<^= 24) {"
    echo "   process.stdout.write('--experimental-wasm-stack-switching');"
    echo "}"
)> "%NODE_CHECK_JS%"

REM Run Node.js and capture the output (the dynamic argument) into NODE_ARGS.
REM Redirect to a file rather than reading a pipe with FOR /F, so %ERRORLEVEL%
REM below is node's own and not the loop body's, and read it before del runs.
node "%NODE_CHECK_JS%" > "%NODE_CHECK_OUT%"
set "NODE_CHECK_STATUS=%ERRORLEVEL%"

set "NODE_ARGS="
if exist "%NODE_CHECK_OUT%" set /p NODE_ARGS=<"%NODE_CHECK_OUT%"

del "%NODE_CHECK_JS%" "%NODE_CHECK_OUT%" 2>nul

if not "%NODE_CHECK_STATUS%"=="0" (
    echo Node.js version check failed or exited with error. >&2
    exit /b 1
)

REM Delayed expansion eats any "!" in the arguments below, so leave it here and
REM carry over the values the call still needs.
endlocal & set "NODE_ARGS=%NODE_ARGS%" & set "RESOLVED_DIR=%RESOLVED_DIR%" & set "THIS_PROGRAM=%THIS_PROGRAM%"

REM Compute our own path, not following symlinks and pass it in so that
REM node_entry.mjs can set sys.executable correctly.
REM Intentionally allow word splitting on %NODEFLAGS%.
node %NODEFLAGS% %NODE_ARGS% "%RESOLVED_DIR%python_cli_entry.mjs" --this-program="%THIS_PROGRAM%" %*

exit /b %ERRORLEVEL%
