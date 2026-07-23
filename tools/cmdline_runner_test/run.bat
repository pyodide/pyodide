@echo on
setlocal enabledelayedexpansion

REM Get the current directory as PYODIDE_ROOT
set PYODIDE_ROOT=%CD%
echo %PYODIDE_ROOT%

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

REM Build pyodide_build
call pip install -e ../pyodide-build
if errorlevel 1 exit /b 1

REM Create pyodide virtual environment
call pyodide venv .venv-pyodide
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
REM Deselect tests that fail on Python 3.15.
REM TODO: remove skips when attrs releases a version compatible with Python 3.15
python -m pytest -k "not mypy" --deselect "tests/test_make.py::TestClassBuilder::test_no_references_to_original_when_using_cached_property" --deselect "tests/test_validators.py::TestMatchesRe::test_catches_invalid_func"
if errorlevel 1 exit /b 1

endlocal
