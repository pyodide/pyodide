def test_numpy(selenium_standalone):
    selenium = selenium_standalone
    selenium.load_package('pytest')
    selenium.load_package('numpy')
    selenium.load_package('nose')
    selenium.run('from pathlib import Path')
    selenium.run('import numpy')
    selenium.run('import pytest')
    selenium.run('base_dir = Path(numpy.__file__).parent')
    try:
        selenium.run("pytest.main(['--continue-on-collection-errors', '-v',"
                     "             base_dir / 'core/tests/test_numeric.py'])")
    except Exception as exc: # noqa
        print('Exception', print(exc))
    print('# Logs')
    logs = '\n'.join(selenium.logs)
    print(logs)
