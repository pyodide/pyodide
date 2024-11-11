import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.parametrize("input_sr, output_sr", [(44100, 22050), (22050, 44100)])
@run_in_pyodide(packages=["soxr", "numpy"])
def test_resample(selenium, input_sr, output_sr):
    import numpy as np
    import soxr

    # Signal length in seconds
    length = 5.0
    # Frequency in Hz
    frequency = 42

    input_sample_positions = np.arange(0, length, 1 / input_sr)
    output_sample_positions = np.arange(0, length, 1 / output_sr)

    input_signal = np.sin(2 * np.pi * frequency * input_sample_positions)
    predicted_output_signal = np.sin(2 * np.pi * frequency * output_sample_positions)

    output_signal = soxr.resample(input_signal, input_sr, output_sr)

    np.testing.assert_allclose(predicted_output_signal, output_signal, atol=0.0015)
