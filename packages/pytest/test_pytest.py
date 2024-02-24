def test_pytest(selenium):
    # TODO: don't use numpy in this test as it's not necessarily installed.
    selenium.load_package(["pytest", "numpy"])

    selenium.run(
        """
        from pathlib import Path
        import os
        import numpy
        import pytest

        base_dir = Path(numpy.__file__).parent / "core" / "tests"
        """
    )

    selenium.run("pytest.main([str(base_dir / 'test_api.py')])")

    logs = "\n".join(selenium.logs)
    assert "INTERNALERROR" not in logs
