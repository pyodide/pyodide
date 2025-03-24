from conftest import run_in_pyodide


def test_openai(selenium):
    from pathlib import Path

    test_openai_inner = (Path(__file__).parent / "helper_test_openai.py").read_text()
    helper_test_openai(selenium, test_openai_inner)


@run_in_pyodide(packages=["openai", "pytest_httpx", "pytest-asyncio"])
async def helper_test_openai(selenium, test_openai_inner):
    from pathlib import Path

    import pytest

    Path("test_openai.py").write_text(test_openai_inner)
    pytest.main(["test_openai.py"])
