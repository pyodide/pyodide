import gzip
import io
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

import boto3
import pytest
from moto import mock_s3

sys.path.append(str(Path(__file__).parents[1]))
from deploy_s3 import check_s3_object_exists, deploy_to_s3_main


@mock_s3
def test_check_s3_object_exists():
    bucket_name = "mybucket"
    s3_client = boto3.client("s3", region_name="us-east-1")
    s3_client.create_bucket(Bucket=bucket_name)

    s3_client.put_object(Bucket=bucket_name, Key="/a/test.txt", Body="test")

    assert check_s3_object_exists(s3_client, bucket_name, "/a/test.txt") is True
    assert check_s3_object_exists(s3_client, bucket_name, "/a/test2.txt") is False


@mock_s3
def test_deploy_to_s3_overwrite(tmp_path, capsys):
    (tmp_path / "a.whl").write_text("a")
    (tmp_path / "b.tar").write_text("b")
    (tmp_path / "c.zip").write_text("c")

    bucket_name = "mybucket"
    s3_client = boto3.client("s3", region_name="us-east-1")
    s3_client.create_bucket(Bucket=bucket_name)

    deploy_to_s3_main(
        tmp_path,
        remote_prefix=PurePosixPath("dev/full/"),
        bucket=bucket_name,
        cache_control="max-age=30758400",
        pretend=False,
        overwrite=False,
        rm_remote_prefix=False,
        access_key_env="AWS_ACCESS_KEY_ID",
        secret_key_env="AWS_SECRET_ACCESS_KEY",
    )

    def get_object_list():
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="dev/full/")
        return set(obj["Key"] for obj in response["Contents"])

    assert get_object_list() == {"dev/full/a.whl", "dev/full/b.tar", "dev/full/c.zip"}

    # Writing a second time to the same prefix with overwrite=False should fail
    with pytest.raises(Exception):
        deploy_to_s3_main(
            tmp_path,
            remote_prefix=PurePosixPath("dev/full/"),
            bucket=bucket_name,
            cache_control="max-age=30758400",
            pretend=False,
            overwrite=False,
            rm_remote_prefix=False,
            access_key_env="AWS_ACCESS_KEY_ID",
            secret_key_env="AWS_SECRET_ACCESS_KEY",
        )
    msg = "Cannot upload .* because it already exists"
    captured = capsys.readouterr()
    # Check for error message in last two lines of output
    assert re.search(msg, "\n".join(captured.out.splitlines()[-2:]))

    # Setting overwrite=True should overwrite the files
    deploy_to_s3_main(
        tmp_path,
        remote_prefix=PurePosixPath("dev/full/"),
        bucket=bucket_name,
        cache_control="max-age=30758400",
        pretend=False,
        overwrite=True,
        rm_remote_prefix=False,
        access_key_env="AWS_ACCESS_KEY_ID",
        secret_key_env="AWS_SECRET_ACCESS_KEY",
    )
    assert get_object_list() == {"dev/full/a.whl", "dev/full/b.tar", "dev/full/c.zip"}

    # Setting rm_remote_prefix=True, should remove remote files that don't exist locally
    (tmp_path / "b.tar").unlink()

    deploy_to_s3_main(
        tmp_path,
        remote_prefix=PurePosixPath("dev/full/"),
        bucket=bucket_name,
        cache_control="max-age=30758400",
        pretend=False,
        overwrite=False,
        rm_remote_prefix=True,
        access_key_env="AWS_ACCESS_KEY_ID",
        secret_key_env="AWS_SECRET_ACCESS_KEY",
    )
    assert get_object_list() == {"dev/full/c.zip", "dev/full/a.whl"}


@mock_s3
def test_deploy_to_s3_mime_type(tmp_path, capsys):
    """Test that we set the correct MIME type for each file extension"""
    for ext in ["whl", "tar", "zip", "js", "ts", "json", "ttf", "a", "mjs.map", "mjs"]:
        (tmp_path / f"a.{ext}").write_text("a")

    bucket_name = "mybucket"
    s3_client = boto3.client("s3", region_name="us-east-1")
    s3_client.create_bucket(Bucket=bucket_name)

    deploy_to_s3_main(
        tmp_path,
        remote_prefix=PurePosixPath(""),
        bucket=bucket_name,
        cache_control="max-age=30758400",
        pretend=False,
        overwrite=False,
        rm_remote_prefix=False,
        access_key_env="AWS_ACCESS_KEY_ID",
        secret_key_env="AWS_SECRET_ACCESS_KEY",
    )

    def get_header(key, field="content-type"):
        res = s3_client.get_object(Bucket=bucket_name, Key=key)
        return res["ResponseMetadata"]["HTTPHeaders"][field]

    assert get_header("a.js", "content-encoding") == "gzip"

    # These  MIME types we set explicitly for better CDN compression
    assert get_header("a.whl") == "application/wasm"
    assert get_header("a.tar") == "application/wasm"
    assert get_header("a.zip") == "application/wasm"
    assert get_header("a.a") == "application/wasm"

    # The rest we set based on the file extension
    assert get_header("a.js") == "text/javascript"
    assert get_header("a.mjs") == "text/javascript"
    assert get_header("a.ts") == "text/x.typescript"
    assert get_header("a.json") == "application/json"
    assert get_header("a.ttf") == "font/ttf"
    assert get_header("a.mjs.map") == "binary/octet-stream"

    # Test that we can read the data back
    res = s3_client.get_object(Bucket=bucket_name, Key="a.js")
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=res["Body"], mode="r") as fh:
        shutil.copyfileobj(fh, stream)
    assert stream.getvalue() == b"a"
