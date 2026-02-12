import os
import time
import uuid

import pytest

from conftest import only_node


@pytest.fixture(scope="function")
def selenium_nodesock(selenium_standalone_noload):
    selenium = selenium_standalone_noload

    selenium.run_js("""
    pyodide = await loadPyodide({
        withNodeSocket: true,
    });
    """)
    yield selenium


# When running this test locally, consider using the following command to start a
# temporary MongoDB server in a Docker container:
# docker run -d --name mongodb-server -p 27017:27017 mongo:7.0
@pytest.fixture(scope="session")
def mongodb_admin_config():
    host = os.environ.get("MONGODB_HOST", "127.0.0.1")
    port = int(os.environ.get("MONGODB_PORT", 27017))  # noqa: PLW1508
    user = os.environ.get("MONGODB_ROOT_USER", "")
    password = os.environ.get("MONGODB_ROOT_PASSWORD", "")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
    }


@pytest.fixture()
def mongodb_test_db(mongodb_admin_config):
    pytest.importorskip("pymongo")
    import asyncio

    suffix = uuid.uuid4().hex[:10]
    db_name = f"pyodide_it_{suffix}"

    # Build connection string
    host = mongodb_admin_config["host"]
    port = mongodb_admin_config["port"]
    user = mongodb_admin_config["user"]
    password = mongodb_admin_config["password"]

    if user and password:
        conn_str = f"mongodb://{user}:{password}@{host}:{port}/"
    else:
        conn_str = f"mongodb://{host}:{port}/"

    # Wait for MongoDB to be ready
    deadline = time.time() + 10
    last_err: Exception | None = None

    async def check_connection():
        from pymongo import AsyncMongoClient

        client = AsyncMongoClient(conn_str, serverSelectionTimeoutMS=2000)
        await client.admin.command("ping")
        await client.close()

    while time.time() < deadline:
        try:
            asyncio.run(check_connection())
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)

    if last_err is not None:
        raise RuntimeError("MongoDB server not reachable within timeout") from last_err

    # Database will be created on first write, no explicit creation needed
    try:
        yield {
            "host": host,
            "port": port,
            "db": db_name,
            "conn_str": conn_str,
        }
    finally:
        # Cleanup: drop the test database
        async def cleanup():
            try:
                from pymongo import AsyncMongoClient

                client = AsyncMongoClient(conn_str, serverSelectionTimeoutMS=2000)
                await client.drop_database(db_name)
                await client.close()
            except Exception:  # noqa: BLE001, S110
                pass  # Best effort cleanup

        try:
            asyncio.run(cleanup())
        except Exception:  # noqa: BLE001, S110
            pass


def _load_pymongo(selenium_nodesock):
    selenium_nodesock.run_js('await pyodide.loadPackage("pymongo");')


@pytest.mark.skip_refcount_check
@pytest.mark.mongodb
@only_node
def test_mongodb_crud(selenium_nodesock, mongodb_test_db):
    cfg = mongodb_test_db
    db_name = cfg["db"]
    conn_str = cfg["conn_str"]

    _load_pymongo(selenium_nodesock)

    # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
    selenium_nodesock.run_js(
        f'''
        await pyodide.runPythonAsync(`
            from pymongo import AsyncMongoClient
            import pymongo

            client = AsyncMongoClient("{conn_str}")
            db = client["{db_name}"]
            collection = db.test_crud

            # Create
            insert_result = await collection.insert_one({{"name": "alpha", "value": 1}})
            assert insert_result.acknowledged

            # Read
            doc = await collection.find_one({{"name": "alpha"}})
            assert doc["name"] == "alpha"
            assert doc["value"] == 1

            # Update
            await collection.update_one({{"name": "alpha"}}, {{"$set": {{"value": 11}}}})
            updated_doc = await collection.find_one({{"name": "alpha"}})
            assert updated_doc["value"] == 11

            # Insert another and query multiple
            await collection.insert_one({{"name": "beta", "value": 2}})
            cursor = collection.find().sort("value", pymongo.ASCENDING)
            docs = await cursor.to_list(length=None)
            assert len(docs) == 2
            assert docs[0]["name"] == "beta"
            assert docs[0]["value"] == 2
            assert docs[1]["name"] == "alpha"
            assert docs[1]["value"] == 11

            # Delete
            delete_result = await collection.delete_one({{"name": "beta"}})
            assert delete_result.deleted_count == 1
            remaining = await collection.count_documents({{}})
            assert remaining == 1

            client.close()
        `);
        '''
    )


@pytest.mark.skip_refcount_check
@pytest.mark.mongodb
@only_node
def test_mongodb_bulk_operations(selenium_nodesock, mongodb_test_db):
    cfg = mongodb_test_db
    db_name = cfg["db"]
    conn_str = cfg["conn_str"]

    _load_pymongo(selenium_nodesock)

    # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
    selenium_nodesock.run_js(
        f'''
        await pyodide.runPythonAsync(`
            from pymongo import AsyncMongoClient
            import pymongo

            client = AsyncMongoClient("{conn_str}")
            db = client["{db_name}"]
            collection = db.test_bulk

            # Bulk insert
            docs_to_insert = [
                {{"k": "a", "v": 1}},
                {{"k": "b", "v": 2}},
                {{"k": "c", "v": 3}},
            ]
            bulk_result = await collection.insert_many(docs_to_insert)
            assert len(bulk_result.inserted_ids) == 3

            # Query bulk inserts
            cursor = collection.find().sort("k", pymongo.ASCENDING)
            docs = await cursor.to_list(length=None)
            assert len(docs) == 3
            assert docs[0]["k"] == "a" and docs[0]["v"] == 1
            assert docs[1]["k"] == "b" and docs[1]["v"] == 2
            assert docs[2]["k"] == "c" and docs[2]["v"] == 3

            # Bulk update
            update_result = await collection.update_many(
                {{"v": {{"$gte": 2}}}},
                {{"$inc": {{"v": 10}}}}
            )
            assert update_result.modified_count == 2

            # Verify updates
            cursor = collection.find().sort("k", pymongo.ASCENDING)
            updated = await cursor.to_list(length=None)
            assert updated[0]["v"] == 1   # "a" unchanged
            assert updated[1]["v"] == 12  # "b" incremented
            assert updated[2]["v"] == 13  # "c" incremented

            client.close()
        `);
        '''
    )


@pytest.mark.skip_refcount_check
@pytest.mark.mongodb
@only_node
def test_mongodb_aggregation(selenium_nodesock, mongodb_test_db):
    cfg = mongodb_test_db
    db_name = cfg["db"]
    conn_str = cfg["conn_str"]

    _load_pymongo(selenium_nodesock)

    # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
    selenium_nodesock.run_js(
        f'''
        await pyodide.runPythonAsync(`
            from pymongo import AsyncMongoClient

            client = AsyncMongoClient("{conn_str}")
            db = client["{db_name}"]
            collection = db.test_agg

            await collection.insert_many([
                {{"category": "fruit", "name": "apple", "price": 1.5}},
                {{"category": "fruit", "name": "banana", "price": 0.5}},
                {{"category": "vegetable", "name": "carrot", "price": 1.0}},
                {{"category": "fruit", "name": "cherry", "price": 2.0}},
            ])

            pipeline = [
                {{"$match": {{"category": "fruit"}}}},
                {{"$group": {{
                    "_id": "$category",
                    "avg_price": {{"$avg": "$price"}},
                    "count": {{"$sum": 1}},
                }}}},
            ]
            cursor = await collection.aggregate(pipeline)
            agg_result = await cursor.to_list(length=None)
            assert len(agg_result) == 1
            assert agg_result[0]["count"] == 3
            assert abs(agg_result[0]["avg_price"] - 4.0 / 3) < 0.01

            client.close()
        `);
        '''
    )


@pytest.mark.skip_refcount_check
@pytest.mark.mongodb
@only_node
def test_mongodb_indexing(selenium_nodesock, mongodb_test_db):
    cfg = mongodb_test_db
    db_name = cfg["db"]
    conn_str = cfg["conn_str"]

    _load_pymongo(selenium_nodesock)

    # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
    selenium_nodesock.run_js(
        f'''
        await pyodide.runPythonAsync(`
            from pymongo import AsyncMongoClient
            import pymongo

            client = AsyncMongoClient("{conn_str}")
            db = client["{db_name}"]
            collection = db.test_index

            await collection.insert_many([
                {{"username": "user1", "email": "user1@example.com"}},
                {{"username": "user2", "email": "user2@example.com"}},
            ])

            # Create unique index
            index_name = await collection.create_index(
                [("username", pymongo.ASCENDING)], unique=True
            )
            assert index_name == "username_1"

            # List indexes (_id index + username index)
            cursor = await collection.list_indexes()
            indexes = await cursor.to_list(length=None)
            assert len(indexes) >= 2

            client.close()
        `);
        '''
    )
