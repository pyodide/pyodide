
# mypy: ignore-errors
from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["protobuf"])
def test_protobuf(selenium):
    from google.protobuf.descriptor_pb2 import FieldDescriptorProto
    from google.protobuf.proto_builder import MakeSimpleProtoClass


    MakeSimpleProtoClass({"field1": FieldDescriptorProto.TYPE_INT64,
                          "field2": FieldDescriptorProto.TYPE_INT64})
