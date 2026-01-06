@echo on
setlocal enabledelayedexpansion

REM Get the current directory as PYODIDE_ROOT
set PYODIDE_ROOT=%CD%
echo %PYODIDE_ROOT%

REM Build pyodide_build
pip install -e ./pyodide-build
if errorlevel 1 exit /b 1

REM Clean up and create test directory
if exist test-cmdline-runner rmdir /s /q test-cmdline-runner
mkdir test-cmdline-runner
cd test-cmdline-runner
if errorlevel 1 exit /b 1

REM Create host virtual environment
python -m venv .venv-host
if errorlevel 1 exit /b 1

REM Activate host virtual environment
call .venv-host\Scripts\activate.bat
if errorlevel 1 exit /b 1

REM Create pyodide virtual environment
pyodide venv .venv-pyodide
if errorlevel 1 exit /b 1

REM Activate pyodide virtual environment
call .venv-pyodide\Scripts\activate.bat
if errorlevel 1 exit /b 1

REM Clone attrs repository
git clone https://github.com/python-attrs/attrs --depth 1 --branch 25.3.0
if errorlevel 1 exit /b 1

cd attrs
if errorlevel 1 exit /b 1

REM Install attrs with tests dependencies
call pip install ".[tests]"
if errorlevel 1 exit /b 1

REM Uninstall pytest-mypy-plugins
call pip uninstall pytest-mypy-plugins -y
if errorlevel 1 exit /b 1

REM Run pytest
python -m pytest -k "not mypy"
if errorlevel 1 exit /b 1

endlocal
