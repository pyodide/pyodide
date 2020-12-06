def test_pytest(selenium):
    selenium.load_package(["pytest", "numpy", "nose"])

    selenium.run(
        """
        from pathlib import Path
        import os
        import numpy
        import pytest

        base_dir = Path(numpy.__file__).parent / "core" / "tests"
        """
    )

    selenium.run("pytest.main([base_dir / 'test_api.py'])")

    logs = "\n".join(selenium.logs)
    assert "INTERNALERROR" not in logs
