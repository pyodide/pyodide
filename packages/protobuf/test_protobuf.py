# mypy: ignore-errors
from pytest_pyodide.decorator import run_in_pyodide


@run_in_pyodide(packages=["protobuf"])
def test_protobuf(selenium):
    from google.protobuf.descriptor_pb2 import FieldDescriptorProto
    from google.protobuf.internal import api_implementation
    from google.protobuf.proto_builder import MakeSimpleProtoClass

    _message = api_implementation._c_module
    assert _message is not None  # check presence of binary component

    SampleObject = MakeSimpleProtoClass(
        {
            "field1": FieldDescriptorProto.TYPE_INT64,
            "field2": FieldDescriptorProto.TYPE_INT64,
        }
    )

    sample = SampleObject()
    sample.field1 = 1
    sample.field2 = 2

    assert repr(sample) == "field1: 1\nfield2: 2\n"


@run_in_pyodide(packages=["protobuf"])
def test_generated_protobuf_code(selenium):
    """
    This tests whether the package works with a generated _pb2.py file.
    It uses the addressbook.proto from here:
    https://github.com/protocolbuffers/protobuf/blob/main/examples/addressbook.proto
    After generation some small modifications have been made to fit the tests.
    It doesn't create any new globals for example.
    """
    from google.protobuf import descriptor_pool as _descriptor_pool
    from google.protobuf import symbol_database as _symbol_database
    from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2
    from google.protobuf.internal import builder as _builder

    _sym_db = _symbol_database.Default()

    assert google_dot_protobuf_dot_timestamp__pb2  # silence flake8 by "using it"

    DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
        b'\n\x11\x61\x64\x64ressbook.proto\x12\x08tutorial\x1a\x1fgoogle/protobuf/timestamp.proto"\x87\x02\n\x06Person\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\n\n\x02id\x18\x02 \x01(\x05\x12\r\n\x05\x65mail\x18\x03 \x01(\t\x12,\n\x06phones\x18\x04 \x03(\x0b\x32\x1c.tutorial.Person.PhoneNumber\x12\x30\n\x0clast_updated\x18\x05 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x1aG\n\x0bPhoneNumber\x12\x0e\n\x06number\x18\x01 \x01(\t\x12(\n\x04type\x18\x02 \x01(\x0e\x32\x1a.tutorial.Person.PhoneType"+\n\tPhoneType\x12\n\n\x06MOBILE\x10\x00\x12\x08\n\x04HOME\x10\x01\x12\x08\n\x04WORK\x10\x02"/\n\x0b\x41\x64\x64ressBook\x12 \n\x06people\x18\x01 \x03(\x0b\x32\x10.tutorial.PersonB\x95\x01\n\x1b\x63om.example.tutorial.protosB\x11\x41\x64\x64ressBookProtosP\x01Z:github.com/protocolbuffers/protobuf/examples/go/tutorialpb\xaa\x02$Google.Protobuf.Examples.AddressBookb\x06proto3'
    )

    _globals = {}  # use a regular dict instead of the actual globals
    _builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
    _builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "addressbook_pb2", _globals)

    # normally this would simply be person = Person(),
    # but we intentionally don't modify globals here
    person = _globals["Person"]()
    person.name = "test"
    person.id = 1
    assert repr(person) == 'name: "test"\nid: 1\n'
