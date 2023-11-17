import pytest
from pytest_pyodide import run_in_pyodide


@pytest.mark.parametrize(
    "name, line_type",
    [
        ("mpl2005", "SeparateCode"),
        ("mpl2014", "SeparateCode"),
        ("serial", "Separate"),
        ("serial", "SeparateCode"),
        ("serial", "ChunkCombinedCode"),
        ("serial", "ChunkCombinedOffset"),
        ("serial", "ChunkCombinedNan"),
        ("threaded", "Separate"),
        ("threaded", "SeparateCode"),
        ("threaded", "ChunkCombinedCode"),
        ("threaded", "ChunkCombinedOffset"),
        ("threaded", "ChunkCombinedNan"),
    ],
)
@run_in_pyodide(packages=["contourpy", "numpy"])
def test_line(selenium, name, line_type):
    import numpy as np
    from contourpy import LineType, contour_generator
    from numpy.testing import assert_array_almost_equal, assert_array_equal

    z = [[1.5, 1.5, 0.9, 0.0], [1.5, 2.8, 0.4, 0.8], [0.0, 0.0, 0.8, 6.0]]

    cont_gen = contour_generator(z=z, name=name, line_type=line_type)
    assert cont_gen.line_type.name == line_type
    assert cont_gen.chunk_count == (1, 1)
    assert cont_gen.thread_count == 1

    lines = cont_gen.lines(2.0)

    expect0 = np.array(
        [
            [0.38461538, 1.0],
            [1.0, 0.38461538],
            [1.33333333, 1.0],
            [1.0, 1.28571429],
            [0.38461538, 1.0],
        ]
    )
    if name in ("mpl2005", "mpl2014"):
        expect0 = np.vstack((expect0[1:], expect0[1]))  # Starts with index 1

    expect1 = np.array([[2.23076923, 2.0], [3.0, 1.23076923]])
    if name == "mpl2005":
        expect1 = expect1[::-1]

    if cont_gen.line_type == LineType.Separate:
        points = lines
        assert len(points) == 2
        assert_array_almost_equal(points[0], expect0)
        assert_array_almost_equal(points[1], expect1)
    elif cont_gen.line_type == LineType.SeparateCode:
        points, codes = lines
        assert len(points) == 2
        if name == "mpl2014":
            points = points[::-1]
            codes = codes[::-1]
        assert_array_almost_equal(points[0], expect0)
        assert_array_almost_equal(points[1], expect1)
        assert_array_equal(codes[0], [1, 2, 2, 2, 79])
        assert_array_equal(codes[1], [1, 2])
    elif cont_gen.line_type == LineType.ChunkCombinedCode:
        assert len(lines[0]) == 1  # Single chunk.
        points, codes = lines[0][0], lines[1][0]
        assert points.shape == (7, 2)
        assert_array_almost_equal(points[:5], expect0)
        assert_array_almost_equal(points[5:], expect1)
        assert_array_equal(codes, [1, 2, 2, 2, 79, 1, 2])
    elif cont_gen.line_type == LineType.ChunkCombinedOffset:
        assert len(lines[0]) == 1  # Single chunk.
        points, offsets = lines[0][0], lines[1][0]
        assert points.shape == (7, 2)
        assert_array_almost_equal(points[:5], expect0)
        assert_array_almost_equal(points[5:], expect1)
        assert_array_equal(offsets, [0, 5, 7])
    elif cont_gen.line_type == LineType.ChunkCombinedNan:
        assert len(lines[0]) == 1  # Single chunk.
        points = lines[0][0]
        assert points.shape == (8, 2)
        assert_array_almost_equal(points[:5], expect0)
        assert np.all(np.isnan(points[5, :]))
        assert_array_almost_equal(points[6:], expect1)
    else:
        raise RuntimeError(f"Unexpected line_type {line_type}")


@pytest.mark.parametrize(
    "name, fill_type",
    [
        ("mpl2005", "OuterCode"),
        ("mpl2014", "OuterCode"),
        ("serial", "OuterCode"),
        ("serial", "OuterOffset"),
        ("serial", "ChunkCombinedCode"),
        ("serial", "ChunkCombinedOffset"),
        ("serial", "ChunkCombinedCodeOffset"),
        ("serial", "ChunkCombinedOffsetOffset"),
        ("threaded", "OuterCode"),
        ("threaded", "OuterOffset"),
        ("threaded", "ChunkCombinedCode"),
        ("threaded", "ChunkCombinedOffset"),
        ("threaded", "ChunkCombinedCodeOffset"),
        ("threaded", "ChunkCombinedOffsetOffset"),
    ],
)
@run_in_pyodide(packages=["contourpy", "numpy"])
def test_fill(selenium, name, fill_type):
    import numpy as np
    from contourpy import FillType, contour_generator
    from numpy.testing import assert_array_almost_equal, assert_array_equal

    z = [[1.5, 1.5, 0.9, 0.0], [1.5, 2.8, 0.4, 0.8], [0.0, 0.0, 0.8, 1.9]]

    cont_gen = contour_generator(z=z, name=name, fill_type=fill_type)
    assert cont_gen.fill_type.name == fill_type
    assert cont_gen.chunk_count == (1, 1)
    assert cont_gen.thread_count == 1

    filled = cont_gen.filled(1.0, 2.0)

    expect0 = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.83333333, 0.0],
            [1.75, 1.0],
            [1.0, 1.64285714],
            [0.0, 1.33333333],
            [0.0, 1.0],
            [0.0, 0.0],
            [1.0, 0.38461538],
            [0.38461538, 1.0],
            [1.0, 1.28571429],
            [1.33333333, 1.0],
            [1.0, 0.38461538],
        ]
    )
    if name == "mpl2014":
        expect0 = np.vstack((expect0[1:8], expect0[1], expect0[9:], expect0[9]))

    expect1 = np.array(
        [[2.18181818, 2.0], [3.0, 1.18181818], [3.0, 2.0], [2.18181818, 2.0]]
    )
    if name in ("mpl2005", "mpl2014"):
        expect1 = np.vstack((expect1[1:], expect1[1]))  # Starts with index 1

    # Helper functions to avoid code duplication for the different FillTypes.
    def assert_outer_points(points):
        assert isinstance(points, list) and len(points) == 2
        assert_array_almost_equal(points[0], expect0)
        assert_array_almost_equal(points[1], expect1)

    def assert_chunk_points(points):
        assert isinstance(points, list) and len(points) == 1
        assert points[0].shape == (17, 2)
        assert_array_almost_equal(points[0][:13], expect0)
        assert_array_almost_equal(points[0][13:], expect1)

    def assert_chunk_codes(codes):
        assert isinstance(codes, list) and len(codes) == 1
        assert_array_equal(
            codes[0], [1, 2, 2, 2, 2, 2, 2, 79, 1, 2, 2, 2, 79, 1, 2, 2, 79]
        )

    def assert_chunk_offsets(offsets):
        assert isinstance(offsets, list) and len(offsets) == 1
        assert_array_equal(offsets[0], [0, 8, 13, 17])

    if cont_gen.fill_type == FillType.OuterCode:
        assert_outer_points(filled[0])
        codes = filled[1]
        assert isinstance(codes, list) and len(codes) == 2
        assert_array_equal(codes[0], [1, 2, 2, 2, 2, 2, 2, 79, 1, 2, 2, 2, 79])
        assert_array_equal(codes[1], [1, 2, 2, 79])
    elif cont_gen.fill_type == FillType.OuterOffset:
        assert_outer_points(filled[0])
        offsets = filled[1]
        assert isinstance(offsets, list) and len(offsets) == 2
        assert_array_equal(offsets[0], [0, 8, 13])
        assert_array_equal(offsets[1], [0, 4])
    elif cont_gen.fill_type == FillType.ChunkCombinedCode:
        assert_chunk_points(filled[0])
        assert_chunk_codes(filled[1])
    elif cont_gen.fill_type == FillType.ChunkCombinedOffset:
        assert_chunk_points(filled[0])
        assert_chunk_offsets(filled[1])
    elif cont_gen.fill_type == FillType.ChunkCombinedCodeOffset:
        assert_chunk_points(filled[0])
        assert_chunk_codes(filled[1])

        outer_offsets = filled[2]
        assert isinstance(outer_offsets, list) and len(outer_offsets) == 1
        assert_array_equal(outer_offsets[0], [0, 13, 17])
    elif cont_gen.fill_type == FillType.ChunkCombinedOffsetOffset:
        assert_chunk_points(filled[0])
        assert_chunk_offsets(filled[1])

        outer_offsets = filled[2]
        assert isinstance(outer_offsets, list) and len(outer_offsets) == 1
        assert_array_equal(outer_offsets[0], [0, 2, 3])
    else:
        raise RuntimeError(f"Unexpected fill_type {fill_type}")
