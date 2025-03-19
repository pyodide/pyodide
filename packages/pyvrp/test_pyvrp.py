from pytest_pyodide import run_in_pyodide

@run_in_pyodide(packages=["pyvrp"])
def test_pyvrp_model_test(selenium):
    import pyvrp
    model = pyvrp.Model()

    depot = model.add_depot(0, 0)
    client = model.add_client(0, 1, delivery=1)
    model.add_edge(depot, client, 1, 1)
    model.add_edge(client, depot, 1, 1)
    model.add_vehicle_type(capacity=1, num_available=1)

    data = model.data()
    assert data.num_clients == 1
    assert data.num_vehicle_types == 1
    assert data.num_vehicles == 1
