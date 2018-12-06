from textwrap import dedent

import pytest


def test_networkx_basicgraph(selenium_standalone, request):
    selenium = selenium_standalone

    if selenium.browser == 'chrome':
        request.applymarker(pytest.mark.xfail(
            run=False, reason='chrome not supported'))

    selenium.load_package(['networkx', 'numpy'])
    cmd = dedent(r"""
        import networkx as nx
        from numpy.testing import assert_equal

        G = nx.Graph()
        G.add_nodes_from([1,2,3])
        G.add_edges_from([(1,2), (1,3)])

        assert_equal(3, G.number_of_nodes())
        assert_equal(2, G.number_of_edges())
        """)

    selenium.run(cmd)
