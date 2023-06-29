# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from pathlib import Path

import asyncio
import click
import fastapi
import pkg_resources
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pixano.apps.core import app, settings

LOGO = """
                             ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒
                           ▒▓▒                                       ▓
              █▓          ▓▓                                         ▓
                        ▒▓▒   ▒▓▓▓▓▓ ▒▓   ▓▒▒▓▓▓▓▒     ▒▓▓▓▓▓▒       ▓
▓▓ ▓▓▓▓▓▓▒    ▓▒  ▒▓   ▓▒   ▒▓      ▓██   ██     ▓▒  ▒█▓     ▒█▓     ▓
███      ▓▓   █▒   ▓█      ▒█▒       ██   █▒     ▒█  ▓▒        █     ▓
██        █▒  █▒    ▒█▓     █▒       ██   █▒     ▒█  ▓▓        █     ▓
██        █▒  █▒    ▓█▓█     █▒     ▓██   █▒     ▒█   ██     ▓█▒     ▓
██▓▒    ▒▓▒   █▒   ▓▒  ▒█▓    ▒▓▓▓▓▓ ▒▓   ▓      ▒▓    ▒▓▓▓▓▓▒       ▓
██  ▒▓▓▒▒     ▒   ▒      ▒▓▒                                         ▓
██                         █▓                                        ▓
"""
ASSETS_PATH = pkg_resources.resource_filename("pixano", "apps/explorer/dist/assets")
TEMPLATE_PATH = pkg_resources.resource_filename("pixano", "apps/explorer/dist")


def main(library_dir: str, host: str = "127.0.0.1", port: int = 8000):
    """Run Pixano Annotator app

    Args:
        library_dir (str): Dataset library directory
        host (str, optional): App host. Defaults to "127.0.0.1".
        port (int, optional): App port. Defaults to 8000.
    """

    templates = Jinja2Templates(directory=TEMPLATE_PATH)
    settings.data_dir = Path(library_dir)

    @app.get("/", response_class=HTMLResponse)
    def main(request: fastapi.Request):
        return templates.TemplateResponse("index.html", {"request": request})

    app.mount("/assets", StaticFiles(directory=ASSETS_PATH), name="assets")
    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)

    loop = asyncio.get_event_loop()
    loop.create_task(server.serve())


@click.command(context_settings={"auto_envvar_prefix": "UVICORN"})
@click.argument(
    "library_dir",
    type=str,
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Bind socket to this host.",
    show_default=True,
)
@click.option(
    "--port",
    type=int,
    default=0,
    help="Bind socket to this port.",
    show_default=True,
)
def command_line(library_dir: str, host: str, port: int):
    """Launch Pixano Explorer

    LIBRARY_DIR: Dataset library directory
    """
    main(library_dir, host, port)


if __name__ == "__main__":
    main()
