from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["pydantic"])
def test_pydantic(selenium):
    import json
    from datetime import datetime

    import pydantic

    class NestedModel(pydantic.BaseModel):
        a: int

    class PydanticModel(pydantic.BaseModel):
        f_str: str
        f_int: int
        f_float: float
        f_datetime: datetime
        f_list: list[int]
        f_dict: dict[str, int]
        f_nested: NestedModel

    m = PydanticModel(
        f_str=b"hello",
        f_int="123",
        f_float="3.14",
        f_datetime="2021-01-01T00:00:00",
        f_list=(1, 2, 3),
        f_dict={"a": 1, "b": "2"},
        f_nested={"a": b"1"},
    )
    expected_dict = {
        "f_str": "hello",
        "f_int": 123,
        "f_float": 3.14,
        "f_datetime": datetime(2021, 1, 1, 0, 0),
        "f_list": [1, 2, 3],
        "f_dict": {"a": 1, "b": 2},
        "f_nested": {"a": 1},
    }
    assert m.model_dump() == expected_dict
    m_json = PydanticModel.model_validate_json(
        '{"f_str":"hello","f_int":123,"f_float":3.14,"f_datetime":"2021-01-01T00:00:00","f_list":[1,2,3],'
        '"f_dict":{"a":1,"b":2},"f_nested":{"a":1}}'
    )
    assert m_json.model_dump() == expected_dict

    assert json.loads(m.model_dump_json()) == {
        "f_str": "hello",
        "f_int": 123,
        "f_float": 3.14,
        "f_datetime": "2021-01-01T00:00:00",
        "f_list": [1, 2, 3],
        "f_dict": {"a": 1, "b": 2},
        "f_nested": {"a": 1},
    }

    assert PydanticModel.model_json_schema() == {
        "$defs": {
            "NestedModel": {
                "properties": {"a": {"title": "A", "type": "integer"}},
                "required": ["a"],
                "title": "NestedModel",
                "type": "object",
            }
        },
        "properties": {
            "f_str": {"title": "F Str", "type": "string"},
            "f_int": {"title": "F Int", "type": "integer"},
            "f_float": {"title": "F Float", "type": "number"},
            "f_datetime": {
                "format": "date-time",
                "title": "F Datetime",
                "type": "string",
            },
            "f_list": {
                "items": {"type": "integer"},
                "title": "F List",
                "type": "array",
            },
            "f_dict": {
                "additionalProperties": {"type": "integer"},
                "title": "F Dict",
                "type": "object",
            },
            "f_nested": {"$ref": "#/$defs/NestedModel"},
        },
        "required": [
            "f_str",
            "f_int",
            "f_float",
            "f_datetime",
            "f_list",
            "f_dict",
            "f_nested",
        ],
        "title": "PydanticModel",
        "type": "object",
    }
