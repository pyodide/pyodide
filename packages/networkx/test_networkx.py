from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["networkx"])
def test_networkx_basicgraph(selenium_standalone):
    import networkx as nx

    G = nx.Graph()
    G.add_nodes_from([1, 2, 3])
    G.add_edges_from([(1, 2), (1, 3)])

    assert G.number_of_nodes() == 3
    assert G.number_of_edges() == 2
