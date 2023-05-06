import gzip
import io
import mimetypes
import os
import shutil
from pathlib import Path

import boto3
import botocore
import typer

app = typer.Typer()


def check_s3_object_exists(s3_client, bucket: str, object_name: str):
    try:
        s3_client.head_object(Bucket=bucket, Key=object_name)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False

        raise


def _validate_remote_prefix_to_remove(remote_prefix: Path) -> None:
    """Check remote prefix to remove

    Examples
    --------
    >>> _validate_remote_prefix_to_remove(Path("dev/full/"))
    >>> _validate_remote_prefix_to_remove(Path("dev/abc2/"))
    >>> _validate_remote_prefix_to_remove(Path("/"))
    Traceback (most recent call last):
    ValueError: Remote prefix to remove should be at least 2 levels deep. For example, 'dev/full/'
    >>> _validate_remote_prefix_to_remove(Path("v0.17.0/full/"))
    Traceback (most recent call last):
    ValueError: Remote prefix to remove should start with 'dev' (without leading '/'). For example, 'dev/full/'
    """
    prefix_parts = remote_prefix.parts
    if len(prefix_parts) < 2:
        raise ValueError(
            "Remote prefix to remove should be at least 2 levels deep. "
            "For example, 'dev/full/'"
        )
    if prefix_parts[0] != "dev":
        raise ValueError(
            "Remote prefix to remove should start with 'dev' (without leading '/'). "
            "For example, 'dev/full/'"
        )


def _rm_s3_prefix(bucket: str, prefix: str):
    """Remove all objects under a given prefix"""
    s3 = boto3.resource("s3")
    bucket = s3.Bucket(bucket)
    for obj in bucket.objects.filter(Prefix=prefix):
        obj.delete()


@app.command()
def deploy_to_s3_main(
    local_folder: Path = typer.Argument(..., help="Path to the local folder"),
    remote_prefix: Path = typer.Argument(..., help="Remote prefix"),
    bucket: str = typer.Option(..., help="bucket name"),
    cache_control: str = typer.Option(
        "max-age=30758400, immutable, public", help="Cache control header to set"
    ),
    pretend: bool = typer.Option(False, help="Don't actually upload anything"),
    overwrite: bool = typer.Option(False, help="Overwrite existing files"),
    rm_remote_prefix: bool = typer.Option(
        False, help="Remove existing files under the remote prefix"
    ),
    access_key_env: str = typer.Option(
        "AWS_ACCESS_KEY_ID", help="Environment variable name for AWS access key"
    ),
    secret_key_env: str = typer.Option(
        "AWS_SECRET_ACCESS_KEY", help="Environment variable name for AWS secret key"
    ),
):
    """Deploy a dist folder with Pyodide packages to AWS S3"""
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=os.environ[access_key_env],
        aws_secret_access_key=os.environ[secret_key_env],
    )

    typer.echo(f"Deploying {local_folder} to s3://{bucket}/{remote_prefix}")
    typer.echo("Options: ")
    typer.echo(f" - {cache_control=}")
    typer.echo(f" - {pretend=}")
    typer.echo(" - content-encoding: gzip")

    if rm_remote_prefix:
        _validate_remote_prefix_to_remove(remote_prefix)
        if not pretend:
            _rm_s3_prefix(bucket, str(remote_prefix).lstrip("/"))

    for file_path in local_folder.glob("**/*"):
        if not file_path.is_file():
            continue
        remote_path = remote_prefix / file_path.relative_to(local_folder)

        if not overwrite and check_s3_object_exists(
            s3_client, bucket, str(remote_path).lstrip("/")
        ):
            typer.echo(
                f"Cannot upload {file_path} because it already exists on s3://{bucket}/{remote_path}"
            )
            typer.echo("Exiting (use --overwrite to overwrite existing files)")
            raise typer.Exit()

        with open(file_path, "rb") as fh_in:
            compressed = file_path.suffix in (".gz", ".bz2")

            if compressed:
                # If the file is already compressed, we don't need to
                # re-compress it.
                typer.echo(f"{file_path} is already compressed, skipping compression")
                fh_compressed = fh_in
            else:
                # Use gzip compression for storage. This only impacts storage on
                # AWS and transfer between S3 and the CDN. It has no impact on the
                # compression received by the end user (since the CDN re-compresses
                # files).
                fh_compressed = io.BytesIO()
                with gzip.GzipFile(fileobj=fh_compressed, mode="wb") as gzip_file:
                    shutil.copyfileobj(fh_in, gzip_file)

                fh_compressed.seek(0)

            content_type = None
            if file_path.suffix in (".zip", ".whl", ".tar", ".a"):
                content_type = "application/wasm"
            elif file_path.suffix == ".ts":
                # This will not be correctly detected by mimetypes.
                # However, JsDelivr will currently not serve .ts file in the
                # custom CDN configuration, so it does not really matter.
                content_type = "text/x.typescript"
            else:
                content_type = mimetypes.guess_type(file_path)[0]
                if content_type is None:
                    content_type = "binary/octet-stream"

            extra_args = {
                "CacheControl": cache_control,
                "ContentType": content_type,
            }

            if not compressed:
                extra_args["ContentEncoding"] = "gzip"

            if not pretend:
                s3_client.upload_fileobj(
                    fh_compressed,
                    Bucket=bucket,
                    Key=str(remote_path).lstrip("/"),
                    ExtraArgs=extra_args,
                )
            msg = (
                f"Uploaded {file_path} to s3://{bucket}/{remote_path} ({content_type=})"
            )
            if pretend:
                msg = "Would have " + msg

            typer.echo(msg)
    if pretend:
        typer.echo(
            "No files were actually uploaded. Set to pretend=False to upload files."
        )


if __name__ == "__main__":
    app()
