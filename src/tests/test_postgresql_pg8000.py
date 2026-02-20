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


# When running this test locally, start a PostgreSQL server with md5 auth:
#   docker run -d --name postgres-server -e POSTGRES_PASSWORD=test -e POSTGRES_HOST_AUTH_METHOD=md5 -e POSTGRES_INITDB_ARGS="--auth-host=md5" -p 5432:5432 postgres:16
# Note: md5 auth is required because Pyodide's hashlib lacks pbkdf2_hmac
# which is needed for PostgreSQL's default scram-sha-256 authentication.
@pytest.fixture(scope="session")
def pg_admin_config():
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = int(os.environ.get("POSTGRES_PORT", 5432))  # noqa: PLW1508
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "test")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
    }


@pytest.fixture()
def pg_test_db(pg_admin_config):
    pg8000 = pytest.importorskip("pg8000")

    suffix = uuid.uuid4().hex[:10]
    db = f"pyodide_it_{suffix}"
    user = f"pyodide_u_{suffix}"
    password = f"pyodide_pw_{suffix}"

    deadline = time.time() + 10
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            conn = pg8000.connect(
                host=pg_admin_config["host"],
                port=pg_admin_config["port"],
                user=pg_admin_config["user"],
                password=pg_admin_config["password"],
            )
            conn.close()
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)

    if last_err is not None:
        raise RuntimeError(
            "PostgreSQL server not reachable within timeout"
        ) from last_err

    def admin_connect():
        conn = pg8000.connect(
            host=pg_admin_config["host"],
            port=pg_admin_config["port"],
            user=pg_admin_config["user"],
            password=pg_admin_config["password"],
        )
        conn.autocommit = True
        return conn

    conn = admin_connect()
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE USER {user} WITH PASSWORD '{password}'")
        cur.execute(f"CREATE DATABASE {db} OWNER {user}")
        cur.close()
    finally:
        conn.close()

    try:
        yield {
            "host": pg_admin_config["host"],
            "port": pg_admin_config["port"],
            "db": db,
            "user": user,
            "password": password,
        }
    finally:
        conn = admin_connect()
        try:
            cur = conn.cursor()
            # Terminate active connections before dropping
            cur.execute(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{db}' AND pid <> pg_backend_pid()
            """)
            cur.execute(f"DROP DATABASE IF EXISTS {db}")
            cur.execute(f"DROP USER IF EXISTS {user}")
            cur.close()
        finally:
            conn.close()


@pytest.mark.skip_refcount_check
@pytest.mark.db
@only_node
def test_postgresql_pg8000_features(selenium_nodesock, pg_test_db):
    cfg = pg_test_db

    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    db = cfg["db"]

    # TODO(pytest-pyodide): Make selenium_standalone_noload support run_in_pyodide
    selenium_nodesock.run_js(
        f'''
        await pyodide.loadPackage("micropip");
        const result = await pyodide.runPythonAsync(`
            import micropip

            await micropip.install("pg8000")

            import pg8000.dbapi

            def connect(**kwargs):
                conn = pg8000.dbapi.connect(
                    host="{host}",
                    port={port},
                    user="{user}",
                    password="{password}",
                    database="{db}",
                    **kwargs,
                )
                return conn

            results = {{}}

            # 1) Basic DDL/DML
            conn = connect()
            conn.autocommit = True
            try:
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS pyodide_pg_test")
                cur.execute(
                    """
                    CREATE TABLE pyodide_pg_test (
                      id SERIAL PRIMARY KEY,
                      name TEXT NOT NULL,
                      value INT NOT NULL
                    )
                    """
                )
                cur.execute(
                    "INSERT INTO pyodide_pg_test (name, value) VALUES (%s, %s)",
                    ("alpha", 1),
                )
                cur.execute(
                    "INSERT INTO pyodide_pg_test (name, value) VALUES (%s, %s)",
                    ("beta", 2),
                )
                cur.execute(
                    "UPDATE pyodide_pg_test SET value = value + 10 WHERE name = %s",
                    ("alpha",),
                )
                cur.execute("SELECT name, value FROM pyodide_pg_test ORDER BY id")
                results["roundtrip"] = cur.fetchall()
                cur.close()
            finally:
                conn.close()

            # 2) Transactions + savepoints
            conn = connect()
            conn.autocommit = False
            try:
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS tx_test")
                cur.execute(
                    "CREATE TABLE tx_test (id SERIAL PRIMARY KEY, name TEXT NOT NULL)"
                )
                conn.commit()

                cur.execute("INSERT INTO tx_test (name) VALUES (%s)", ("rolled_back",))
                conn.rollback()

                cur.execute("SELECT COUNT(*) FROM tx_test")
                after_rollback = cur.fetchone()[0]

                cur.execute("INSERT INTO tx_test (name) VALUES (%s)", ("kept",))
                cur.execute("SAVEPOINT sp1")
                cur.execute("INSERT INTO tx_test (name) VALUES (%s)", ("dropped",))
                cur.execute("ROLLBACK TO SAVEPOINT sp1")
                conn.commit()

                cur.execute("SELECT name FROM tx_test ORDER BY id")
                names = [row[0] for row in cur.fetchall()]
                cur.close()

                results["tx"] = {{"after_rollback": after_rollback, "names": names}}
            finally:
                conn.close()

            # 3) executemany + column metadata
            conn = connect()
            conn.autocommit = True
            try:
                cur = conn.cursor()
                cur.execute("DROP TABLE IF EXISTS bulk_test")
                cur.execute(
                    """
                    CREATE TABLE bulk_test (
                      id SERIAL PRIMARY KEY,
                      k TEXT NOT NULL UNIQUE,
                      v INT NOT NULL
                    )
                    """
                )
                rows = [("a", 1), ("b", 2), ("c", 3)]
                cur.executemany(
                    "INSERT INTO bulk_test (k, v) VALUES (%s, %s)", rows
                )
                cur.execute("SELECT k, v FROM bulk_test ORDER BY k")
                cols = [desc[0] for desc in cur.description]
                raw = cur.fetchall()
                out = [dict(zip(cols, row)) for row in raw]
                cur.close()
                results["bulk"] = {{"inserted": len(rows), "out": out}}
            finally:
                conn.close()
            results
        `);

        assert(() => result.roundtrip.length === 2);
        assert(() => result.roundtrip[0][0] === "alpha");
        assert(() => result.roundtrip[0][1] === 11);
        assert(() => result.roundtrip[1][0] === "beta");
        assert(() => result.roundtrip[1][1] === 2);
        assert(() => result.tx.after_rollback === 0);
        assert(() => result.tx.names[0] === "kept");
        assert(() => result.bulk.inserted === 3);
        assert(() => result.bulk.out.length === 3);
        assert(() => result.bulk.out[0].k === "a");
        assert(() => result.bulk.out[0].v === 1);
        assert(() => result.bulk.out[1].k === "b");
        assert(() => result.bulk.out[1].v === 2);
        assert(() => result.bulk.out[2].k === "c");
        assert(() => result.bulk.out[2].v === 3);
        '''
    )
