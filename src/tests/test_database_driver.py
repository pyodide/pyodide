"""
This test file is for testing database drivers with Node.js socket support.

All the tests are disabled by default and need to be run manually with `-m db` flag.
"""

import os
import time
import uuid

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_node

pytestmark = [
    pytest.mark.requires_dynamic_linking,
    only_node,
]


def _sql_string_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


@pytest.fixture(scope="function")
def selenium_nodesock(selenium_standalone, runtime):
    # only_node marker doesn't work in fixture level...
    if runtime != "node":
        pytest.skip("Only works in node")

    selenium = selenium_standalone

    selenium.run_js(
        """
        await pyodide.useNodeSockFS();
        """
    )
    yield selenium


@pytest.fixture(scope="session")
def mysql_admin_config():
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    user = os.environ.get("MYSQL_ROOT_USER", "root")
    password = os.environ.get("MYSQL_ROOT_PASSWORD", "")

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
    }


@pytest.fixture()
def mysql_test_db(mysql_admin_config):
    import cryptography  # noqa: F401  # for mysql_native_password
    import pymysql  # type: ignore[import-untyped]

    suffix = uuid.uuid4().hex[:10]
    db = f"pyodide_it_{suffix}"
    user = f"pyodide_u_{suffix}"
    password = f"pyodide_pw_{suffix}"

    deadline = time.time() + 10
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            conn = pymysql.connect(
                host=mysql_admin_config["host"],
                port=mysql_admin_config["port"],
                user=mysql_admin_config["user"],
                password=mysql_admin_config["password"],
                autocommit=True,
            )
            conn.close()
            last_err = None
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)

    if last_err is not None:
        raise RuntimeError("MySQL server not reachable within timeout") from last_err

    def admin_connect():
        return pymysql.connect(
            host=mysql_admin_config["host"],
            port=mysql_admin_config["port"],
            user=mysql_admin_config["user"],
            password=mysql_admin_config["password"],
            autocommit=True,
        )

    conn = admin_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{db}`")
            pw = _sql_string_literal(password)
            try:
                cur.execute(
                    f"CREATE USER '{user}'@'%' IDENTIFIED WITH mysql_native_password BY '{pw}'"
                )
            except pymysql.err.OperationalError as e:  # noqa: BLE001
                if e.args and e.args[0] == 1524:
                    cur.execute(f"CREATE USER '{user}'@'%' IDENTIFIED BY '{pw}'")
                else:
                    raise
            cur.execute(f"GRANT ALL PRIVILEGES ON `{db}`.* TO '{user}'@'%'")
            cur.execute("FLUSH PRIVILEGES")
    finally:
        conn.close()

    try:
        yield {
            "host": mysql_admin_config["host"],
            "port": mysql_admin_config["port"],
            "db": db,
            "user": user,
            "password": password,
        }
    finally:
        conn = admin_connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS `{db}`")
                cur.execute(f"DROP USER IF EXISTS '{user}'@'%'")
                cur.execute("FLUSH PRIVILEGES")
        finally:
            conn.close()


# When running mysql test locally, run MySQL server in a Docker container:
#   docker run -d --name mysql-server -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -p 3306:3306 mysql:8.0.0
#   pip install pymysql cryptography
#   pytest src/tests/test_database_driver.py::test_mysql_pymysql_features -m db
# Using MySQL 8.0 is helpful to use Native Pluggable Authentication which simplifies testing.
@pytest.mark.skip_refcount_check
@pytest.mark.db
@only_node
def test_mysql_pymysql_features(selenium_nodesock, mysql_test_db):
    cfg = mysql_test_db

    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    db = cfg["db"]

    @run_in_pyodide(packages=["micropip"])
    async def run(selenium, host, port, user, password, db):
        import micropip

        await micropip.install("pymysql==1.1.0")

        import pymysql

        def connect(**kwargs):
            return pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                unix_socket=False,
                **kwargs,
            )

        results = {}

        # 1) Basic DDL/DML
        conn = connect(autocommit=True)
        try:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS pyodide_mysql_test")
                cur.execute(
                    """
                    CREATE TABLE pyodide_mysql_test (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        name VARCHAR(255) NOT NULL,
                        value INT NOT NULL
                    )
                    """
                )
                cur.execute(
                    "INSERT INTO pyodide_mysql_test (name, value) VALUES (%s, %s)",
                    ("alpha", 1),
                )
                cur.execute(
                    "INSERT INTO pyodide_mysql_test (name, value) VALUES (%s, %s)",
                    ("beta", 2),
                )
                cur.execute(
                    "UPDATE pyodide_mysql_test SET value = value + 10 WHERE name = %s",
                    ("alpha",),
                )
                cur.execute("SELECT name, value FROM pyodide_mysql_test ORDER BY id")
                results["roundtrip"] = cur.fetchall()
        finally:
            conn.close()

        # 2) Transactions + savepoints
        conn = connect(autocommit=False)
        try:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS tx_test")
                cur.execute(
                    "CREATE TABLE tx_test (id INT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(50) NOT NULL)"
                )
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

            results["tx"] = {"after_rollback": after_rollback, "names": names}
        finally:
            conn.close()

        # 3) executemany + DictCursor
        conn = connect(cursorclass=pymysql.cursors.DictCursor)
        try:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS bulk_test")
                cur.execute(
                    """
                    CREATE TABLE bulk_test (
                        id INT PRIMARY KEY AUTO_INCREMENT,
                        k VARCHAR(50) NOT NULL UNIQUE,
                        v INT NOT NULL
                    )
                    """
                )
                rows = [("a", 1), ("b", 2), ("c", 3)]
                cur.executemany("INSERT INTO bulk_test (k, v) VALUES (%s, %s)", rows)
                inserted = cur.rowcount
                cur.execute("SELECT k, v FROM bulk_test ORDER BY k")
                out = cur.fetchall()
            results["bulk"] = {"inserted": inserted, "out": out}
        finally:
            conn.close()

        assert len(results["roundtrip"]) == 2
        assert results["roundtrip"][0][0] == "alpha"
        assert results["roundtrip"][0][1] == 11
        assert results["roundtrip"][1][0] == "beta"
        assert results["roundtrip"][1][1] == 2
        assert results["tx"]["after_rollback"] == 0
        assert results["tx"]["names"][0] == "kept"
        assert results["bulk"]["inserted"] == 3
        assert len(results["bulk"]["out"]) == 3
        assert results["bulk"]["out"][0]["k"] == "a"
        assert results["bulk"]["out"][0]["v"] == 1
        assert results["bulk"]["out"][1]["k"] == "b"
        assert results["bulk"]["out"][1]["v"] == 2
        assert results["bulk"]["out"][2]["k"] == "c"
        assert results["bulk"]["out"][2]["v"] == 3

    run(selenium_nodesock, host, port, user, password, db)


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
    import pg8000

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


# When running this test locally, start a PostgreSQL server and install dependencies:
#   docker run -d --name postgres-server -e POSTGRES_PASSWORD=test -e POSTGRES_HOST_AUTH_METHOD=md5 -e POSTGRES_INITDB_ARGS="--auth-host=md5" -p 5432:5432 postgres:16
#   pip install pg8000
#   pytest src/tests/test_database_driver.py::test_postgresql_pg8000_features -m db
# Note: md5 auth is required because Pyodide's hashlib lacks pbkdf2_hmac
# which is needed for PostgreSQL's default scram-sha-256 authentication.
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

    @run_in_pyodide(packages=["micropip"])
    async def run(selenium, host, port, user, password, db):
        import micropip

        await micropip.install("pg8000")

        import pg8000.dbapi

        def connect(**kwargs):
            conn = pg8000.dbapi.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                **kwargs,
            )
            return conn

        results = {}

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

            results["tx"] = {"after_rollback": after_rollback, "names": names}
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
            cur.executemany("INSERT INTO bulk_test (k, v) VALUES (%s, %s)", rows)
            cur.execute("SELECT k, v FROM bulk_test ORDER BY k")
            cols = [desc[0] for desc in cur.description]
            raw = cur.fetchall()
            out = [dict(zip(cols, row, strict=True)) for row in raw]
            cur.close()
            results["bulk"] = {"inserted": len(rows), "out": out}
        finally:
            conn.close()

        assert results["roundtrip"] == (["alpha", 11], ["beta", 2])
        assert results["tx"]["after_rollback"] == 0
        assert results["tx"]["names"] == ["kept"]
        assert results["bulk"]["inserted"] == 3
        assert results["bulk"]["out"] == [
            {"k": "a", "v": 1},
            {"k": "b", "v": 2},
            {"k": "c", "v": 3},
        ]

    run(selenium_nodesock, host, port, user, password, db)
