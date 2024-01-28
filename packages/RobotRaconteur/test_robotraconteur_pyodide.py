from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["RobotRaconteur", "numpy"])
def test_robotraconteur_import(selenium):
    from RobotRaconteur.Client import RRN

    _ = RRN.RobotRaconteurVersion


@run_in_pyodide(packages=["RobotRaconteur", "numpy"])
def test_robotraconteur_exceptions(selenium):
    import pytest
    import RobotRaconteur as RR

    RRN = RR.RobotRaconteurNode.s
    RRN.SetNodeName("test_node")
    assert RRN.NodeName == "test_node"
    with pytest.raises(Exception):  # noqa: B017
        RRN.SetNodeName("test_node")
