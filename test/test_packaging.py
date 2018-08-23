def test_pytest(selenium):
    selenium.load_package('pytest')
    selenium.load_package('pandas')
    selenium.run('from pathlib import Path')
    selenium.run('import os')
    selenium.run('import pandas as pd')
    selenium.run('base_dir = Path(pd.__file__).parent / "tests" / "frame"')
    selenium.run('print(base_dir)')
    selenium.run('print(list(sorted(os.listdir(base_dir))))')
    selenium.run("import pytest;"
                 "pytest.main([base_dir / 'test_sorting.py'])")
