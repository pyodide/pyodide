import pytest
from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pymongo"])
def test_pymongo_basic(selenium):
    # Socket/network related features are tested separately.
    # This file is intended to be a smoke test for functionality that does not
    # require opening sockets.

    import datetime

    import pymongo
    from bson import ObjectId, json_util
    from bson.codec_options import CodecOptions
    from bson.son import SON
    from pymongo import MongoClient
    from pymongo.errors import InvalidURI
    from pymongo.read_preferences import ReadPreference
    from pymongo.uri_parser import parse_uri
    from pymongo.write_concern import WriteConcern

    assert isinstance(pymongo.version, str)
    assert pymongo.version.count(".") >= 1

    # BSON ObjectId roundtrip
    oid = ObjectId()
    assert len(str(oid)) == 24
    assert ObjectId(str(oid)) == oid

    # json_util dumps/loads for BSON types (does not require sockets)
    doc = {"_id": oid, "x": 1, "when": datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)}
    dumped = json_util.dumps(doc)
    loaded = json_util.loads(dumped)
    assert loaded["_id"] == oid
    assert loaded["x"] == 1
    assert loaded["when"].year == 2020

    # SON preserves insertion order
    son = SON([("a", 1), ("b", 2), ("c", 3)])
    assert list(son.keys()) == ["a", "b", "c"]

    # URI parsing (no DNS SRV, no socket)
    parsed = parse_uri("mongodb://user:pass@localhost:27017/mydb?appName=pyodide")
    assert parsed["nodelist"] == [("localhost", 27017)]
    assert parsed["username"] == "user"
    assert parsed["password"] == "pass"
    assert parsed["database"] == "mydb"
    assert parsed["options"]["appname"] == "pyodide"

    try:
        parse_uri("not-a-mongodb-uri")
    except InvalidURI:
        pass
    else:
        assert False, "InvalidURI not raised"

    # Construction of objects should be possible without connecting.
    # `connect=False` prevents an eager connection attempt.
    client = MongoClient("mongodb://localhost:27017", connect=False)
    db = client.get_database("testdb")
    coll = db.get_collection("testcoll")
    assert db.name == "testdb"
    assert coll.name == "testcoll"

    # Option objects exist and can be attached to database/collection objects.
    wc = WriteConcern(w=1)
    rp = ReadPreference.PRIMARY
    codec = CodecOptions(tz_aware=True)

    db2 = client.get_database("testdb2", write_concern=wc, read_preference=rp, codec_options=codec)
    coll2 = db2.get_collection("testcoll2")
    assert db2.codec_options.tz_aware is True
    assert db2.read_preference == ReadPreference.PRIMARY
    assert db2.write_concern.document.get("w") == 1
    assert coll2.full_name == "testdb2.testcoll2"
