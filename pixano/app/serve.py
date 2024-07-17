# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import asyncio
from functools import lru_cache

import click
import fastapi
import pkg_resources  # type: ignore[import-untyped]
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pixano.app.display import display_cli, display_colab, display_ipython
from pixano.app.main import create_app
from pixano.app.settings import Settings, get_settings


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
    """Pixano app.

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
        aws_endpoint: str | None = None,
        aws_region: str | None = None,
        aws_access_key: str | None = None,
        aws_secret_key: str | None = None,
        local_model_dir: str | None = None,
        host: str = "127.0.0.1",
        port: int = 8000,
    ):
        """Initialize and run Pixano app.

        Args:
            library_dir (str): Local or S3 path to dataset library
            aws_endpoint (str | None, optional): S3 endpoint URL, use 'AWS' if not provided.
                Used if library_dir is an S3 path. Defaults to None.
            aws_region (str | None, optional): S3 region name, not always required for
                private storages. Used if library_dir is an S3 path. Defaults to None.
            aws_access_key (str | None, optional): S3 AWS access key. Used if library_dir is
                an S3 path. Defaults to None.
            aws_secret_key (str | None, optional): S3 AWS secret key. Used if library_dir
                is an S3 path. Defaults to None.
            local_model_dir (str | None, optional): Local path to models. Used if library_dir
                is an S3 path. Defaults to None.
            host (str, optional): App host. Defaults to "127.0.0.1".
            port (int, optional): App port. Defaults to 8000.
        """

        # Override app settings
        @lru_cache
        def get_settings_override():
            return Settings(
                library_dir=library_dir,
                aws_endpoint=aws_endpoint,
                aws_region=aws_region,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                local_model_dir=local_model_dir,
            )

        # Create app
        templates = Jinja2Templates(directory=TEMPLATE_PATH)
        self.app = create_app(settings=get_settings_override())
        self.app.dependency_overrides[get_settings] = get_settings_override

        @self.app.get("/", response_class=HTMLResponse)
        def main_page(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        @self.app.get("/{ds_id}/dataset", response_class=HTMLResponse)
        async def dataset_page(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        @self.app.get("/{ds_id}/dashboard", response_class=HTMLResponse)
        async def dashboard_page(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        @self.app.get("/{ds_id}/dataset/{item_id}", response_class=HTMLResponse)
        async def item_page(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        self.app.mount("/_app", StaticFiles(directory=ASSETS_PATH), name="assets")
        self.config = uvicorn.Config(self.app, host=host, port=port)
        self.server = uvicorn.Server(self.config)

        # Serve app
        task_functions[self.get_env()](self.server.serve())  # type: ignore[operator]

    def display(self, height: int = 1000) -> None:
        """Display Pixano app.

        Args:
            height (int, optional): Frame height. Defaults to 1000.
        """
        # Wait for app to be online
        while not self.server.started:
            task_functions[self.get_env()](asyncio.wait(0.1))  # type: ignore[operator, call-overload]

        # Display app
        for server in self.server.servers:
            for socket in server.sockets:
                address = socket.getsockname()
                display_functions[self.get_env()](url=f"http://{address[0]}", port=address[1], height=height)  # type: ignore[operator]

    def get_env(self) -> str:
        """Get the app's current running environment.

        Returns:
            str: Running environment
        """
        # If Google colab import succeeds
        try:
            import google.colab  # noqa: F401, I001
            import IPython
        except ImportError:
            pass
        else:
            if IPython.get_ipython() is not None:
                return "colab"

        # If IPython import succeeds
        try:
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
    "--aws_endpoint",
    type=str,
    help=("S3 endpoint URL, use 'AWS' if not provided. " "Used if library_dir is an S3 path"),
)
@click.option(
    "--aws_region",
    type=str,
    help=("S3 region name, not always required for private storages." "Used if library_dir is an S3 path"),
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
    aws_endpoint: str,
    aws_region: str,
    aws_access_key: str,
    aws_secret_key: str,
    local_model_dir: str,
    host: str,
    port: int,
):
    """Launch Pixano App in LIBRARY_DIR.

    LIBRARY_DIR is the local or S3 path to your dataset library
    """
    App(
        library_dir,
        aws_endpoint,
        aws_region,
        aws_access_key,
        aws_secret_key,
        local_model_dir,
        host,
        port,
    )
