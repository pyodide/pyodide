import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.xfail_browsers(safari="timeout")
@run_in_pyodide(packages=["pyiceberg"])
def test_catalog(selenium):
    import os

    from pyiceberg.catalog.sql import SqlCatalog

    warehouse_path = "/tmp/warehouse"
    catalog_name = "default"
    namespace_name = "default"
    os.makedirs(warehouse_path)

    catalog = SqlCatalog(
        catalog_name,
        **{
            "uri": f"sqlite:///{warehouse_path}/pyiceberg_catalog.db",
            "warehouse": f"file://{warehouse_path}",
        },
    )

    catalog.create_namespace(namespace_name)

    assert catalog_name == catalog.name
    assert namespace_name == catalog.list_namespaces()[0][0]
    assert (
        f"sqlite:///{warehouse_path}/pyiceberg_catalog.db" == catalog.properties["uri"]
    )
    assert f"file://{warehouse_path}" == catalog.properties["warehouse"]
