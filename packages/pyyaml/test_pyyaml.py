from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pyyaml"])
def test_pyyaml(selenium):
    import yaml
    from yaml import CLoader as Loader

    document = """
    - Hesperiidae
    - Papilionidae
    - Apatelodidae
    - Epiplemidae
    """
    loaded = yaml.load(document, Loader=Loader)
    assert loaded == ["Hesperiidae", "Papilionidae", "Apatelodidae", "Epiplemidae"]
