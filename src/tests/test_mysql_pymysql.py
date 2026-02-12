import os
import time
import uuid

import pytest

from conftest import only_node


def _sql_string_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


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
# temporary MySQL server in a Docker container:
# docker run -d --name mysql-server -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -p 3306:3306 mysql:8.0.0
# Using 8.0 is important to use Native Pluggable Authentication which simplifies testing.
@pytest.fixture(scope="session")
def mysql_admin_config():
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = int(os.environ.get("MYSQL_PORT", 3306))  # noqa: PLW1508
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
    pymysql = pytest.importorskip("pymysql")
    pytest.importorskip("cryptography")  # for mysql_native_password

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


@pytest.mark.skip_refcount_check
@pytest.mark.mysql
@only_node
def test_mysql_pymysql_features(selenium_nodesock, mysql_test_db):
    cfg = mysql_test_db

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
            import datetime
            import decimal

            import micropip

            await micropip.install("pymysql==1.1.0")

            import pymysql

            def connect(**kwargs):
                return pymysql.connect(
                    host="{host}",
                    port={port},
                    user="{user}",
                    password="{password}",
                    database="{db}",
                    unix_socket=False,
                    **kwargs,
                )

            results = {{}}

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

                results["tx"] = {{"after_rollback": after_rollback, "names": names}}
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
                results["bulk"] = {{"inserted": inserted, "out": out}}
            finally:
                conn.close()
            results
        `);

        assert(() => result.roundtrip.length === 2);
        console.log(result.roundtrip.toString());
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
