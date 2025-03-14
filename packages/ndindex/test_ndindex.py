from pytest_pyodide import run_in_pyodide


@run_in_pyodide(
    packages=["ndindex"],
)
def test_ndindex_basics(selenium):
    from ndindex import Integer, Slice, Tuple, ndindex

    idx1 = Integer(3)
    idx2 = Slice(1, 10, 2)
    idx3 = Tuple(0, Slice(None, 5))

    # Test that the raw attributes of the basic index types
    # that we just created contain the expected values
    assert idx1.raw == 3
    assert idx2.raw == slice(1, 10, 2)
    assert idx3.raw == (0, slice(None, 5, None))

    assert len(Slice(2, 5)) == 3

    # Test using ndindex constructors.
    assert ndindex(3) == Integer(3)
    assert ndindex[1:5] == Slice(1, 5)
    assert ndindex[2, :5] == Tuple(2, Slice(None, 5))


# Test reduce, newshape, and isvalid methods
@run_in_pyodide(
    packages=["ndindex"],
)
def test_ndindex_methods(selenium):
    from ndindex import Integer, Slice, Tuple

    idx1 = Slice(None, 10, None)
    reduced1 = idx1.reduce()
    assert reduced1 == Slice(0, 10, 1)

    idx2 = Integer(-2)
    reduced2 = idx2.reduce((5,))
    assert reduced2 == Integer(3)

    shape = (5, 6, 7)
    idx3 = Integer(2)
    idx4 = Slice(1, 4)
    idx5 = Tuple(0, Slice(1, 4), ...)

    assert idx3.newshape(shape) == (6, 7)
    assert idx4.newshape(shape) == (3, 6, 7)
    assert idx5.newshape(shape) == (3, 7)

    assert idx3.isvalid((5,))
    assert not idx3.isvalid((2,))


# Test chunking functionality: ChunkSize, indices, num_chunks,
# num_subchunks, containing_block
@run_in_pyodide(
    packages=["ndindex"],
)
def test_ndindex_chunking(selenium):
    from ndindex import ChunkSize, Slice, Tuple

    chunk_size = ChunkSize((10, 10))
    shape = (25, 25)

    assert chunk_size.num_chunks(shape) == 9  # these are 3×3 chunks (ceiling division)

    chunks = list(chunk_size.indices(shape))
    assert len(chunks) == 9

    # The first chunk should be (0:10, 0:10)
    assert chunks[0] == Tuple(Slice(0, 10, 1), Slice(0, 10, 1))

    # The last chunk should be (20:25, 20:25) (as it is the remainder).
    assert chunks[-1] == Tuple(Slice(20, 25, 1), Slice(20, 25, 1))

    idx = Tuple(Slice(5, 15), Slice(5, 15))
    assert chunk_size.num_subchunks(idx, shape) == 4

    block = chunk_size.containing_block(idx, shape)
    assert block == Tuple(Slice(0, 20, 1), Slice(0, 20, 1))
