# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Optional

import typer


server_app = typer.Typer(help="Pixano server commands.")


@server_app.command()
def run(
    data_dir: str = typer.Argument(..., help="Path to data directory (contains library/, media/, models/)."),
    aws_endpoint: Optional[str] = typer.Option(
        None,
        help="S3 endpoint URL, use 'AWS' if not provided. Used if library_dir or media_dir is an S3 path.",
    ),
    aws_region: Optional[str] = typer.Option(
        None,
        help="S3 region name, not always required for private storages. Used if library_dir or media_dir is an S3 path.",
    ),
    aws_access_key: Optional[str] = typer.Option(
        None,
        help="S3 AWS access key. Used if library_dir or media_dir is an S3 path.",
    ),
    aws_secret_key: Optional[str] = typer.Option(
        None,
        help="S3 AWS secret key. Used if library_dir or media_dir is an S3 path.",
    ),
    host: str = typer.Option("127.0.0.1", help="Pixano app URL host."),
    port: int = typer.Option(7492, help="Pixano app URL port."),
    pixano_inference_url: Optional[str] = typer.Option(
        None,
        help="Pixano inference API url.",
    ),
) -> None:
    """Launch the Pixano annotation server."""
    from pixano.app.serve import App

    App(
        data_dir,
        aws_endpoint=aws_endpoint,
        aws_region=aws_region,
        aws_access_key=aws_access_key,
        aws_secret_key=aws_secret_key,
        host=host,
        port=port,
        pixano_inference_url=pixano_inference_url,
    )
