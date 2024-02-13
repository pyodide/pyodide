from pathlib import Path
from typing import cast

import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["aiohttp"])
async def aiohttp_test_helper(selenium, patch, base_url, lock_data):
    exec(patch, {})
    import json

    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(base_url + "/pyodide-lock.json") as response:
            assert response.status == 200
            assert response.headers["content-type"] == "application/json"

            body = await response.json()
            expected = json.loads(lock_data)
            assert body == expected


def test_aiohttp(selenium):
    patch = (Path(__file__).parent / "aiohttp_patch.py").read_text()
    dist_dir = cast(str, pytest.pyodide_dist_dir)  # type:ignore[attr-defined]
    lock_data = (Path(dist_dir) / "pyodide-lock.json").read_text()
    aiohttp_test_helper(selenium, patch, selenium.base_url, lock_data)
