import gzip
import io
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


@app.command()
def deploy_to_s3(
    local_folder: Path = typer.Argument(..., help="Path to the local folder"),
    remote_prefix: Path = typer.Argument(..., help="Remote prefix"),
    bucket: str = typer.Option(..., help="bucket name"),
    cache_control: str = typer.Option(
        "max-age=30758400, immutable, public", help="Cache control header to set"
    ),
    pretend: bool = typer.Option(False, help="Don't actually upload anything"),
    overwrite: bool = typer.Option(False, help="Overwrite existing files"),
):
    """Deploy of local folder with Pyodide packages to AWS S3"""
    s3_client = boto3.client("s3")

    typer.echo(f"Deploying {local_folder} to s3://{bucket}/{remote_prefix}")
    typer.echo("Options: ")
    typer.echo(f" - {cache_control=}")
    typer.echo(f" - {pretend=}")
    typer.echo(" - content-encoding: gzip")

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
            # Use gzip compression for storage. This only impacts storage on
            # AWS and transfer between S3 and the CDN. It has no impact on the
            # compression received by the end user (since the CDN re-compresses
            # files).
            fh_compressed = io.BytesIO()
            with gzip.GzipFile(fileobj=fh_compressed, mode="w"):
                shutil.copyfileobj(fh_in, fh_compressed)

            fh_compressed.seek(0)

            extra_args = {"CacheControl": cache_control, "ContentEncoding": "gzip"}

            content_type = None
            if file_path.suffix in (".zip", ".whl", ".tar"):
                content_type = "application/wasm"
                extra_args["ContentType"] = content_type

            if not pretend:
                s3_client.upload_fileobj(
                    fh_compressed,
                    Bucket=bucket,
                    Key=str(remote_path).lstrip("/"),
                    ExtraArgs=extra_args,
                )
            msg = f"Uploaded {file_path} to s3://{bucket}/{remote_path}"
            if content_type is not None:
                msg += f" with {content_type=}"
            if pretend:
                msg = "Would have " + msg

            typer.echo(msg)
    if pretend:
        typer.echo(
            "No files were actually uploaded. Set to pretend=False to upload files."
        )


if __name__ == "__main__":
    app()
