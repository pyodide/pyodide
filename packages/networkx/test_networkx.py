from pyodide_test_runner import run_in_pyodide


@run_in_pyodide(standalone=True, packages=["networkx"])
def test_networkx_basicgraph():
    import networkx as nx

    G = nx.Graph()
    G.add_nodes_from([1, 2, 3])
    G.add_edges_from([(1, 2), (1, 3)])

    assert G.number_of_nodes() == 3
    assert G.number_of_edges() == 2
