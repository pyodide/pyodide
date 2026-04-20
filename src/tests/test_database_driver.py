"""
This test file is for testing database drivers with Node.js socket support.

All the tests are disabled by default and need to be run manually with `-m db` flag.
"""

import os
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
    import contextlib

    import cryptography  # noqa: F401  # for mysql_native_password
    import pymysql  # type: ignore[import-untyped]

    suffix = uuid.uuid4().hex[:10]
    db = f"pyodide_it_{suffix}"
    user = f"pyodide_u_{suffix}"
    password = f"pyodide_pw_{suffix}"

    def admin_connect():
        conn = pymysql.connect(
            host=mysql_admin_config["host"],
            port=mysql_admin_config["port"],
            user=mysql_admin_config["user"],
            password=mysql_admin_config["password"],
            autocommit=True,
        )
        return contextlib.closing(conn)

    with admin_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{db}`")
            pw = _sql_string_literal(password)
            cur.execute(
                f"CREATE USER '{user}'@'%' IDENTIFIED WITH mysql_native_password BY '{pw}'"
            )
            cur.execute(f"GRANT ALL PRIVILEGES ON `{db}`.* TO '{user}'@'%'")
            cur.execute("FLUSH PRIVILEGES")

    try:
        yield {
            "host": mysql_admin_config["host"],
            "port": mysql_admin_config["port"],
            "db": db,
            "user": user,
            "password": password,
        }
    finally:
        with admin_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS `{db}`")
                cur.execute(f"DROP USER IF EXISTS '{user}'@'%'")
                cur.execute("FLUSH PRIVILEGES")


# When running mysql test locally, run MySQL server in a Docker container:
#   docker run -d --name mysql-server -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -p 3306:3306 mysql:8.0.45
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
        import contextlib

        import micropip

        await micropip.install("pymysql==1.1.0")

        import pymysql

        def connect(**kwargs):
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                unix_socket=False,
                **kwargs,
            )
            return contextlib.closing(conn)

        # 1) Basic DDL/DML
        with connect(autocommit=True) as conn:
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
                result = cur.fetchall()

            assert result == (("alpha", 11), ("beta", 2))

        # 2) Transactions + savepoints
        with connect(autocommit=False) as conn:
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

            assert after_rollback == 0
            assert names == ["kept"]

        # 3) executemany + DictCursor
        with connect(cursorclass=pymysql.cursors.DictCursor) as conn:
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

            assert inserted == 3
            assert len(out) == 3
            assert out == [{"k": "a", "v": 1}, {"k": "b", "v": 2}, {"k": "c", "v": 3}]

    run(selenium_nodesock, host, port, user, password, db)


# SQLAlchemy ORM test — reuses the same MySQL fixture as above.
#   pytest src/tests/test_database_driver.py::test_sqlalchemy_mysql -m db
@pytest.mark.skip_refcount_check
@pytest.mark.db
@only_node
def test_sqlalchemy_mysql(selenium_nodesock, mysql_test_db):
    cfg = mysql_test_db

    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    db = cfg["db"]

    @run_in_pyodide(packages=["micropip"])
    async def run(selenium, host, port, user, password, db):
        import micropip

        await micropip.install(["sqlalchemy", "pymysql==1.1.0"])

        from sqlalchemy import ForeignKey, String, create_engine, func, select
        from sqlalchemy.orm import (
            DeclarativeBase,
            Mapped,
            Session,
            mapped_column,
            relationship,
        )

        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"
        engine = create_engine(url, connect_args={"unix_socket": False})

        class Base(DeclarativeBase):
            pass

        class User(Base):
            __tablename__ = "sa_users"
            id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = mapped_column(String(100))
            addresses: Mapped[list["Address"]] = relationship(
                back_populates="user", cascade="all, delete-orphan"
            )

        class Address(Base):
            __tablename__ = "sa_addresses"
            id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
            email: Mapped[str] = mapped_column(String(200))
            user_id: Mapped[int] = mapped_column(ForeignKey("sa_users.id"))
            user: Mapped["User"] = relationship(back_populates="addresses")

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        # 1) Insert with relationships
        with Session(engine) as s:
            s.add_all(
                [
                    User(
                        name="alice",
                        addresses=[
                            Address(email="alice@example.com"),
                            Address(email="alice@work.com"),
                        ],
                    ),
                    User(
                        name="bob",
                        addresses=[
                            Address(email="bob@example.com"),
                        ],
                    ),
                ]
            )
            s.commit()

            users = s.scalars(select(User).order_by(User.name)).all()
            assert [(u.name, len(u.addresses)) for u in users] == [
                ("alice", 2),
                ("bob", 1),
            ]

        # 2) Update
        with Session(engine) as s:
            alice = s.scalars(select(User).where(User.name == "alice")).one()
            alice.name = "alice_updated"
            s.commit()

            updated = s.scalars(select(User).where(User.name == "alice_updated")).one()
            assert updated.name == "alice_updated"

        # 3) Delete with cascade
        with Session(engine) as s:
            bob = s.scalars(select(User).where(User.name == "bob")).one()
            s.delete(bob)
            s.commit()

            user_count = s.scalar(select(func.count()).select_from(User))
            addr_count = s.scalar(select(func.count()).select_from(Address))
            assert user_count == 1
            assert addr_count == 2

        # 4) Rollback
        with Session(engine) as s:
            s.add(User(name="should_not_exist"))
            s.flush()
            s.rollback()

            count = s.scalar(select(func.count()).select_from(User))
            assert count == 1

        # 5) Join query
        with Session(engine) as s:
            rows = s.execute(
                select(User.name, Address.email)
                .join(Address)
                .order_by(User.name, Address.email)
            ).all()
            assert rows == [
                ("alice_updated", "alice@example.com"),
                ("alice_updated", "alice@work.com"),
            ]

        Base.metadata.drop_all(engine)
        engine.dispose()

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
    import contextlib

    import pg8000

    suffix = uuid.uuid4().hex[:10]
    db = f"pyodide_it_{suffix}"
    user = f"pyodide_u_{suffix}"
    password = f"pyodide_pw_{suffix}"

    def admin_connect():
        conn = pg8000.connect(
            host=pg_admin_config["host"],
            port=pg_admin_config["port"],
            user=pg_admin_config["user"],
            password=pg_admin_config["password"],
        )
        conn.autocommit = True
        return contextlib.closing(conn)

    with admin_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE USER {user} WITH PASSWORD '{password}'")
            cur.execute(f"CREATE DATABASE {db} OWNER {user}")

    try:
        yield {
            "host": pg_admin_config["host"],
            "port": pg_admin_config["port"],
            "db": db,
            "user": user,
            "password": password,
        }
    finally:
        with admin_connect() as conn:
            with conn.cursor() as cur:
                # Terminate active connections before dropping
                cur.execute(f"""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = '{db}' AND pid <> pg_backend_pid()
                """)
                cur.execute(f"DROP DATABASE IF EXISTS {db}")
                cur.execute(f"DROP USER IF EXISTS {user}")


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
        import contextlib

        import micropip

        await micropip.install("pg8000")

        import pg8000

        def connect(**kwargs):
            conn = pg8000.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=db,
                **kwargs,
            )
            return contextlib.closing(conn)

        # 1) Basic DDL/DML
        with connect() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
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
                result = cur.fetchall()

            assert result == (["alpha", 11], ["beta", 2])

        # 2) Transactions + savepoints
        with connect() as conn:
            conn.autocommit = False
            with conn.cursor() as cur:
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

            assert after_rollback == 0
            assert names == ["kept"]

        # 3) executemany + column metadata
        with connect() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
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
                result = cur.fetchall()

            assert result == (["a", 1], ["b", 2], ["c", 3])

    run(selenium_nodesock, host, port, user, password, db)


# SQLAlchemy ORM test — reuses the same PostgreSQL fixture as above.
#   pytest src/tests/test_database_driver.py::test_sqlalchemy_pg8000 -m db
@pytest.mark.skip_refcount_check
@pytest.mark.db
@only_node
def test_sqlalchemy_pg8000(selenium_nodesock, pg_test_db):
    cfg = pg_test_db

    host = cfg["host"]
    port = cfg["port"]
    user = cfg["user"]
    password = cfg["password"]
    db = cfg["db"]

    @run_in_pyodide(packages=["micropip"])
    async def run(selenium, host, port, user, password, db):
        import micropip

        await micropip.install(["sqlalchemy", "pg8000"])

        from sqlalchemy import ForeignKey, String, create_engine, func, select
        from sqlalchemy.orm import (
            DeclarativeBase,
            Mapped,
            Session,
            mapped_column,
            relationship,
        )

        url = f"postgresql+pg8000://{user}:{password}@{host}:{port}/{db}"
        engine = create_engine(url)

        class Base(DeclarativeBase):
            pass

        class User(Base):
            __tablename__ = "sa_users"
            id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = mapped_column(String(100))
            addresses: Mapped[list["Address"]] = relationship(
                back_populates="user", cascade="all, delete-orphan"
            )

        class Address(Base):
            __tablename__ = "sa_addresses"
            id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
            email: Mapped[str] = mapped_column(String(200))
            user_id: Mapped[int] = mapped_column(ForeignKey("sa_users.id"))
            user: Mapped["User"] = relationship(back_populates="addresses")

        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        # 1) Insert with relationships
        with Session(engine) as s:
            s.add_all(
                [
                    User(
                        name="alice",
                        addresses=[
                            Address(email="alice@example.com"),
                            Address(email="alice@work.com"),
                        ],
                    ),
                    User(
                        name="bob",
                        addresses=[
                            Address(email="bob@example.com"),
                        ],
                    ),
                ]
            )
            s.commit()

            users = s.scalars(select(User).order_by(User.name)).all()
            assert [(u.name, len(u.addresses)) for u in users] == [
                ("alice", 2),
                ("bob", 1),
            ]

        # 2) Update
        with Session(engine) as s:
            alice = s.scalars(select(User).where(User.name == "alice")).one()
            alice.name = "alice_updated"
            s.commit()

            updated = s.scalars(select(User).where(User.name == "alice_updated")).one()
            assert updated.name == "alice_updated"

        # 3) Delete with cascade
        with Session(engine) as s:
            bob = s.scalars(select(User).where(User.name == "bob")).one()
            s.delete(bob)
            s.commit()

            user_count = s.scalar(select(func.count()).select_from(User))
            addr_count = s.scalar(select(func.count()).select_from(Address))
            assert user_count == 1
            assert addr_count == 2

        # 4) Rollback
        with Session(engine) as s:
            s.add(User(name="should_not_exist"))
            s.flush()
            s.rollback()

            count = s.scalar(select(func.count()).select_from(User))
            assert count == 1

        # 5) Join query
        with Session(engine) as s:
            rows = s.execute(
                select(User.name, Address.email)
                .join(Address)
                .order_by(User.name, Address.email)
            ).all()
            assert [(name, email) for name, email in rows] == [
                ("alice_updated", "alice@example.com"),
                ("alice_updated", "alice@work.com"),
            ]

        Base.metadata.drop_all(engine)
        engine.dispose()

    run(selenium_nodesock, host, port, user, password, db)
