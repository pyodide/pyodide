"""
Various common utilities for testing.
"""

import pytest

try:
    from pytest_pyodide.fixtures import selenium_standalone as orig_fixture

    @pytest.fixture(scope="session")
    def selenium_standalone(request):
        """Reuse the Selenium session and refresh the page between tests."""
        selenium = orig_fixture(request)
        yield selenium
        # Do not quit the session here; let the session fixture handle cleanup.

    @pytest.fixture(autouse=True)
    def refresh_selenium_standalone(selenium_standalone):
        """Refresh the page between tests to simulate a clean environment."""
        selenium_standalone.browser.refresh()

except ImportError:
    # pytest_pyodide is not available; do not override the fixture.
    pass
