import pytest
from pytest_pyodide.fixture import selenium_context_manager


@pytest.mark.driver_timeout(40)
@pytest.mark.xfail_browsers(
    chrome="Times out in chrome", firefox="Times out in firefox"
)
def test_scikit_bio(selenium_module_scope):
    with selenium_context_manager(selenium_module_scope) as selenium:
        selenium.load_package("scikit-bio")
        assert (
            selenium.run(
                """
                import numpy as np
                import skbio
                """
            )
            > 0
        )
