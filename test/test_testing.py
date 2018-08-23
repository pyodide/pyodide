def test_pytest(selenium):
    selenium.load_package('pytest')
    selenium.load_package('numpy')
    selenium.load_package('nose')
    selenium.run('from pathlib import Path')
    selenium.run('import os')
    selenium.run('import numpy')
    selenium.run('base_dir = Path(numpy.__file__).parent / "core" / "tests"')
    selenium.run('print(base_dir)')
    selenium.run('print(list(sorted(os.listdir(base_dir))))')
    selenium.run("import pytest;"
                 "pytest.main([base_dir / 'test_api.py'])")
    logs = '\n'.join(selenium.logs)
    assert 'INTERNALERROR' not in logs
