from pytest_pyodide import run_in_pyodide


@run_in_pyodide(
    packages=[
        "msprime",
    ]
)
def test_msprime(selenium):
    import msprime
    import tskit

    # basic test
    ts = msprime.sim_ancestry(10, random_seed=42)
    ts.dump("/tmp/msprime.trees")
    ts = tskit.load("/tmp/msprime.trees")
    ts2 = msprime.sim_ancestry(10, random_seed=42)
    ts.tables.assert_equals(ts2.tables, ignore_provenance=True)
