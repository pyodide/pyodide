from pytest_pyodide import run_in_pyodide

SAMPLE_LP = pathlib.Path(__file__).parent / "test_data" / "WhiskasModel.lp"


@run_in_pyodide(packages=["apsw"])
async def highspy_test_helper(selenium, lp_file):
    import highspy

    h = highspy.Highs()
    h.readModel(lp_file)
    h.run()

    model_status = h.modelStatusToString(h.getModelStatus())
    optimal_value = round(h.getInfo().objective_function_value, 2)

    assert model_status == "Optimal"
    assert optimal_value == 0.97


def test_highspy(selenium):
    highspy_test_helper(selenium, SAMPLE_LP)
