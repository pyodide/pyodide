from pyodide_build.testing import run_in_pyodide


@run_in_pyodide(packages=["pyo3_samples"])
def test_pyo3_samples():
    import pyo3_samples
    from unittest import TestCase

    raises = TestCase().assertRaisesRegex

    assert pyo3_samples.multiply(5, 7) == 35
    assert (
        pyo3_samples.count_occurences("the skunk saw the people eat the the.", "the")
        == 4
    )
    assert pyo3_samples.get_fibonacci(13) == 233
    assert pyo3_samples.sum_as_string(4, 9) == "13"
    assert pyo3_samples.list_sum(range(20)) == 190

    with raises(TypeError, "'str' object cannot be interpreted as an integer"):
        pyo3_samples.get_fibonacci("13")

    assert pyo3_samples.human_says_hi('{"name" : "Albert", "age" : 13}') == "Albert"
    assert (
        pyo3_samples.human_says_hi(
            '{"name" : "Joshua", "age" : 11, "address" : "22nd Place"}'
        )
        == "Joshua"
    )
    with raises(
        ValueError,
        "Failed to parse human_data: missing field `age` at line 1 column 19",
    ):
        pyo3_samples.human_says_hi('{"name" : "albert"}')
    with raises(
        ValueError, "Failed to parse human_data: trailing comma at line 1 column 20"
    ):
        pyo3_samples.human_says_hi('{"name" : "albert",}')
