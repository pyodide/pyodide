import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["coolprop"])
def test_simple_propssi(selenium):
    import pytest
    from CoolProp.CoolProp import PropsSI

    assert round(PropsSI("T", "P", 101325, "Q", 0, "Water"), 3) == 373.124

    with pytest.raises(ValueError):
        PropsSI("T", "P", 101325, "Q", 0, "Walter")


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["coolprop"])
def test_simple_phasesi(selenium):
    from CoolProp.CoolProp import PhaseSI

    assert PhaseSI("P", 101325, "Q", 0, "Water") == "twophase"


@pytest.mark.driver_timeout(60)
@run_in_pyodide(packages=["coolprop"])
def test_simple_HAPropsSI(selenium):
    import pytest
    from CoolProp.HumidAirProp import HAPropsSI

    assert round(HAPropsSI("H", "T", 298.15, "P", 101325, "R", 0.5), 3) == 50423.450

    with pytest.raises(ValueError):
        HAPropsSI("H", "T", 298.15, "P", -101325, "R", 0.5)
