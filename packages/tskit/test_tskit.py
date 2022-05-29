from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(
    packages=["numpy", "svgwrite", "attrs", "pyrsistent", "jsonschema", "tskit"]
)
def test_tskit(selenium):
    import tskit

    # basic test
    tc = tskit.TableCollection(2)
    assert tc.sequence_length == 2
    tc.nodes.add_row(flags=tskit.NODE_IS_SAMPLE)
    tc.nodes.add_row(time=1)
    tc.edges.add_row(left=0, right=1, parent=1, child=0)
    tc.edges.add_row(left=1, right=2, parent=1, child=0)
    ts = tc.tree_sequence()
    assert ts.num_nodes == 2

    # save and load
    ts.dump("/tmp/tskit.trees")
    ts2 = tskit.load("/tmp/tskit.trees")
    ts.tables.assert_equals(ts2.tables)

    # test dependency related functions
    ts.draw_svg(size=(200, 200))
    tskit.MetadataSchema({"codec": "json"})
