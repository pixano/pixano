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

import asyncio
from functools import lru_cache

import click
import fastapi
import pkg_resources
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pixano.app.display import display_cli, display_colab, display_ipython
from pixano.app.main import create_app
from pixano.data.settings import Settings, get_settings

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
ASSETS_PATH = pkg_resources.resource_filename("pixano", "app/dist/_app")
TEMPLATE_PATH = pkg_resources.resource_filename("pixano", "app/dist")

task_functions = {
    "colab": asyncio.get_event_loop().create_task,
    "ipython": asyncio.get_event_loop().create_task,
    "none": asyncio.run,
}
display_functions = {
    "colab": display_colab,
    "ipython": display_ipython,
    "none": display_cli,
}


class App:
    """Pixano app

    Attributes:
        app (fastapi.FastAPI): FastAPI App
        config (uvicorn.Config): App config
        server (uvicorn.Server): App server
    """

    app: fastapi.FastAPI
    config: uvicorn.Config
    server: uvicorn.Server

    def __init__(
        self,
        library_dir: str,
        endpoint_url: str = None,
        region_name: str = None,
        aws_access_key: str = None,
        aws_secret_key: str = None,
        local_model_dir: str = None,
        host: str = "127.0.0.1",
        port: int = 8000,
    ):
        """Initialize and run Pixano app

        Args:
            library_dir (str): Local or S3 path to dataset library
            endpoint_url (str, optional): S3 endpoint URL, use 'AWS' if not provided. Used if library_dir is an S3 path. Defaults to None.
            region_name (str, optional): S3 region name, not always required for private storages. Used if library_dir is an S3 path. Defaults to None.
            aws_access_key (str, optional): S3 AWS access key. Used if library_dir is an S3 path. Defaults to None.
            aws_secret_key (str, optional): S3 AWS secret key. Used if library_dir is an S3 path. Defaults to None.
            local_model_dir (str, optional): Local path to models. Used if library_dir is an S3 path. Defaults to None.
            host (str, optional): App host. Defaults to "127.0.0.1".
            port (int, optional): App port. Defaults to 8000.
        """

        # Override app settings
        @lru_cache
        def get_settings_override():
            return Settings(
                library_dir=library_dir,
                endpoint_url=endpoint_url,
                region_name=region_name,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                local_model_dir=local_model_dir,
            )

        # Create app
        templates = Jinja2Templates(directory=TEMPLATE_PATH)
        self.app = create_app(settings=get_settings_override())
        self.app.dependency_overrides[get_settings] = get_settings_override

        @self.app.get("/", response_class=HTMLResponse)
        def app_main(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        self.app.mount("/_app", StaticFiles(directory=ASSETS_PATH), name="assets")
        self.config = uvicorn.Config(self.app, host=host, port=port)
        self.server = uvicorn.Server(self.config)

        # Serve app
        task_functions[self.get_env()](self.server.serve())

    def display(self, height: int = 1000) -> None:
        """Display Pixano app

        Args:
            height (int, optional): Frame height. Defaults to 1000.
        """

        # Wait for app to be online
        while not self.server.started:
            task_functions[self.get_env()](asyncio.wait(0.1))

        # Display app
        for server in self.server.servers:
            for socket in server.sockets:
                address = socket.getsockname()
                display_functions[self.get_env()](
                    url=f"http://{address[0]}", port=address[1], height=height
                )

    def get_env(self) -> str:
        """Get the app's current running environment

        Returns:
            str: Running environment
        """

        # If Google colab import succeeds
        try:
            # pylint: disable=import-outside-toplevel, unused-import
            import google.colab
            import IPython
        except ImportError:
            pass
        else:
            if IPython.get_ipython() is not None:
                return "colab"

        # If IPython import succeeds
        try:
            # pylint: disable=import-outside-toplevel
            import IPython
        except ImportError:
            pass
        else:
            ipython = IPython.get_ipython()
            if ipython is not None and ipython.has_trait("kernel"):
                return "ipython"

        # Else
        return "none"


@click.command(context_settings={"auto_envvar_prefix": "UVICORN"})
@click.argument("library_dir", type=str)
@click.option(
    "--endpoint_url",
    type=str,
    help="S3 endpoint URL, use 'AWS' if not provided. Used if library_dir is an S3 path",
)
@click.option(
    "--region_name",
    type=str,
    help="S3 region name, not always required for private storages. Used if library_dir is an S3 path",
)
@click.option(
    "--aws_access_key",
    type=str,
    help="S3 AWS access key. Used if library_dir is an S3 path",
)
@click.option(
    "--aws_secret_key",
    type=str,
    help="S3 AWS secret key. Used if library_dir is an S3 path",
)
@click.option(
    "--local_model_dir",
    type=str,
    help="Local path to your models. Used if library_dir is an S3 path",
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Pixano app URL host",
    show_default=True,
)
@click.option(
    "--port",
    type=int,
    default=0,
    help="Pixano app URL port",
    show_default=True,
)
def main(
    library_dir: str,
    endpoint_url: str,
    region_name: str,
    aws_access_key: str,
    aws_secret_key: str,
    local_model_dir: str,
    host: str,
    port: int,
):
    """Launch Pixano App in LIBRARY_DIR

    LIBRARY_DIR is the local or S3 path to your dataset library
    """

    App(
        library_dir,
        endpoint_url,
        region_name,
        aws_access_key,
        aws_secret_key,
        local_model_dir,
        host,
        port,
    )
