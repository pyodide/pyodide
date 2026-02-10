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
    pymongo = pytest.importorskip("pymongo")
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
        client.close()

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
                client.close()
            except Exception:  # noqa: BLE001, S110
                pass  # Best effort cleanup

        try:
            asyncio.run(cleanup())
        except Exception:  # noqa: BLE001, S110
            pass


@pytest.mark.skip_refcount_check
@pytest.mark.mongodb
@only_node
def test_mongodb_pymongo_features(selenium_nodesock, mongodb_test_db):
    cfg = mongodb_test_db

    host = cfg["host"]
    port = cfg["port"]
    db_name = cfg["db"]
    conn_str = cfg["conn_str"]

    # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
    selenium_nodesock.run_js(
        f'''
        await pyodide.loadPackage("pymongo");
        const result = await pyodide.runPythonAsync(`
            from pymongo import AsyncMongoClient
            import pymongo
            from bson import ObjectId

            conn_str = "{conn_str}"
            db_name = "{db_name}"

            client = AsyncMongoClient(conn_str)
            db = client[db_name]

            results = {{}}

            # 1) Basic CRUD operations
            collection = db.test_collection
            
            # Create
            insert_result = await collection.insert_one({{"name": "alpha", "value": 1}})
            inserted_id = str(insert_result.inserted_id)
            
            # Read
            doc = await collection.find_one({{"name": "alpha"}})
            results["create_read"] = {{"name": doc["name"], "value": doc["value"]}}
            
            # Update
            await collection.update_one({{"name": "alpha"}}, {{"$set": {{"value": 11}}}})
            updated_doc = await collection.find_one({{"name": "alpha"}})
            results["update"] = updated_doc["value"]
            
            # Insert another document
            await collection.insert_one({{"name": "beta", "value": 2}})
            
            # Query multiple documents
            cursor = collection.find().sort("value", pymongo.ASCENDING)
            docs = await cursor.to_list(length=None)
            results["find_all"] = [{{"name": d["name"], "value": d["value"]}} for d in docs]
            
            # Delete
            delete_result = await collection.delete_one({{"name": "beta"}})
            results["delete_count"] = delete_result.deleted_count
            
            remaining = await collection.count_documents({{}})
            results["remaining_count"] = remaining

            # 2) Bulk operations with insert_many
            bulk_collection = db.bulk_test
            docs_to_insert = [
                {{"k": "a", "v": 1}},
                {{"k": "b", "v": 2}},
                {{"k": "c", "v": 3}},
            ]
            bulk_result = await bulk_collection.insert_many(docs_to_insert)
            results["bulk_inserted"] = len(bulk_result.inserted_ids)
            
            # Query bulk inserts
            cursor = bulk_collection.find().sort("k", pymongo.ASCENDING)
            bulk_docs = await cursor.to_list(length=None)
            results["bulk_out"] = [{{"k": d["k"], "v": d["v"]}} for d in bulk_docs]
            
            # Bulk update
            update_result = await bulk_collection.update_many(
                {{"v": {{"$gte": 2}}}},
                {{"$inc": {{"v": 10}}}}
            )
            results["bulk_updated"] = update_result.modified_count
            
            # Verify updates
            cursor = bulk_collection.find().sort("k", pymongo.ASCENDING)
            updated_docs = await cursor.to_list(length=None)
            results["bulk_updated_out"] = [{{"k": d["k"], "v": d["v"]}} for d in updated_docs]

            # 3) Aggregation pipeline
            agg_collection = db.agg_test
            await agg_collection.insert_many([
                {{"category": "fruit", "name": "apple", "price": 1.5}},
                {{"category": "fruit", "name": "banana", "price": 0.5}},
                {{"category": "vegetable", "name": "carrot", "price": 1.0}},
                {{"category": "fruit", "name": "cherry", "price": 2.0}},
            ])
            
            pipeline = [
                {{"$match": {{"category": "fruit"}}}},
                {{"$group": {{"_id": "$category", "avg_price": {{"$avg": "$price"}}, "count": {{"$sum": 1}}}}}},
            ]
            cursor = agg_collection.aggregate(pipeline)
            agg_result = await cursor.to_list(length=None)
            results["aggregation"] = {{
                "count": agg_result[0]["count"],
                "avg_price": agg_result[0]["avg_price"]
            }}

            # 4) Indexing
            index_collection = db.index_test
            await index_collection.insert_many([
                {{"username": "user1", "email": "user1@example.com"}},
                {{"username": "user2", "email": "user2@example.com"}},
            ])
            
            # Create index
            index_name = await index_collection.create_index([("username", pymongo.ASCENDING)], unique=True)
            results["index_created"] = index_name
            
            # List indexes
            cursor = index_collection.list_indexes()
            indexes = await cursor.to_list(length=None)
            results["index_count"] = len(indexes)

            # Cleanup
            client.close()

            results
        `);

        // Verify results
        console.log("Results:", JSON.stringify(result, null, 2));
        
        // Test 1: Basic CRUD
        assert(() => result.create_read.name === "alpha");
        assert(() => result.create_read.value === 1);
        assert(() => result.update === 11);
        assert(() => result.find_all.length === 2);
        assert(() => result.find_all[0].name === "beta");
        assert(() => result.find_all[0].value === 2);
        assert(() => result.find_all[1].name === "alpha");
        assert(() => result.find_all[1].value === 11);
        assert(() => result.delete_count === 1);
        assert(() => result.remaining_count === 1);
        
        // Test 2: Bulk operations
        assert(() => result.bulk_inserted === 3);
        assert(() => result.bulk_out.length === 3);
        assert(() => result.bulk_out[0].k === "a");
        assert(() => result.bulk_out[0].v === 1);
        assert(() => result.bulk_out[1].k === "b");
        assert(() => result.bulk_out[1].v === 2);
        assert(() => result.bulk_out[2].k === "c");
        assert(() => result.bulk_out[2].v === 3);
        assert(() => result.bulk_updated === 2);
        assert(() => result.bulk_updated_out[0].v === 1);  // "a" unchanged
        assert(() => result.bulk_updated_out[1].v === 12); // "b" incremented
        assert(() => result.bulk_updated_out[2].v === 13); // "c" incremented
        
        // Test 3: Aggregation
        assert(() => result.aggregation.count === 3);
        assert(() => Math.abs(result.aggregation.avg_price - 1.333) < 0.01);
        
        // Test 4: Indexing
        assert(() => result.index_created === "username_1");
        assert(() => result.index_count >= 2); // _id index + username index
        '''
    )