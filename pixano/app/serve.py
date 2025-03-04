# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import asyncio
import warnings
from functools import lru_cache

import click
import fastapi
import pkg_resources  # type: ignore[import-untyped]
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pixano_inference.client import PixanoInferenceClient

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
    """The Pixano app.

    Attributes:
        app: FastAPI App.
        config: App config.
        server: App server.
    """

    app: fastapi.FastAPI
    config: uvicorn.Config
    server: uvicorn.Server

    def __init__(
        self,
        library_dir: str,
        media_dir: str,
        models_dir: str | None = None,
        aws_endpoint: str | None = None,
        aws_region: str | None = None,
        aws_access_key: str | None = None,
        aws_secret_key: str | None = None,
        host: str = "127.0.0.1",
        port: int = 8000,
        pixano_inference_url: str | None = None,
    ):
        """Initialize and serve the Pixano app.

        Args:
            library_dir: Local or S3 path to dataset library
            media_dir: Local or S3 path to media library
            models_dir: Path to your models. If not provided, and
                library_dir is not a S3 path, it is set to
                library_dir/models.
            aws_endpoint: S3 endpoint URL, use 'AWS' if not provided.
                Used if library_dir is an S3 path.
            aws_region: S3 region name, not always required for
                private storages. Used if library_dir is an S3 path.
            aws_access_key: S3 AWS access key. Used if library_dir is
                an S3 path.
            aws_secret_key: S3 AWS secret key. Used if library_dir
                is an S3 path.
            host: App host.
            port: App port.
            pixano_inference_url: Pixano inference URL if any.
        """

        # Override app settings
        @lru_cache
        def get_settings_override():
            return Settings(
                library_dir=library_dir,
                media_dir=media_dir,
                models_dir=models_dir,
                aws_endpoint=aws_endpoint,
                aws_region=aws_region,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                pixano_inference_client=PixanoInferenceClient.connect(pixano_inference_url)
                if pixano_inference_url is not None
                else None,
            )

        # Create app
        settings = get_settings_override()
        templates = Jinja2Templates(directory=TEMPLATE_PATH)
        self.app = create_app(settings=settings)
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

        try:
            self.app.mount("/_app", StaticFiles(directory=ASSETS_PATH), name="assets")
        # TODO: properly define environment variable for production to raise a RuntimeError accordingly
        except RuntimeError:
            warnings.warn(
                "Pixano app assets not found. If it is a production environment, this is not expected, "
                "check if you have built the assets for the UI."
            )
        self.config = uvicorn.Config(self.app, host=host, port=port)
        self.server = uvicorn.Server(self.config)

        # Serve app
        task_functions[self.get_env()](self.server.serve())  # type: ignore[operator]

    def display(self, height: int = 1000) -> None:
        """Display the Pixano app.

        Args:
            height: Frame height.
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
            Running environment.
        """
        # If Google colab import succeeds
        try:
            import google.colab  # noqa: F401, I001 #type: ignore
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
@click.argument("media_dir", type=str)
@click.option(
    "--models_dir",
    type=str,
    help="Path to your models. If not provided, and library_dir is not a S3 path, it is set to library_dir/models",
)
@click.option(
    "--aws_endpoint",
    type=str,
    help=("S3 endpoint URL, use 'AWS' if not provided. Used if library_dir or media_dir is an S3 path"),
)
@click.option(
    "--aws_region",
    type=str,
    help=("S3 region name, not always required for private storages. Used if library_dir or media_dir is an S3 path"),
)
@click.option(
    "--aws_access_key",
    type=str,
    help="S3 AWS access key. Used if library_dir or media_dir is an S3 path",
)
@click.option(
    "--aws_secret_key",
    type=str,
    help="S3 AWS secret key. Used if library_dir or media_dir is an S3 path",
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
@click.option("--pixano_inference_url", type=str, help="Pixano inference API url.", default="")
def main(
    library_dir: str,
    media_dir: str,
    models_dir: str,
    aws_endpoint: str,
    aws_region: str,
    aws_access_key: str,
    aws_secret_key: str,
    host: str,
    port: int,
    pixano_inference_url: str,
) -> None:
    """Launch Pixano App in LIBRARY_DIR.

    Args:
        library_dir: Local or S3 path to dataset library.
        media_dir: Local or S3 path to media library.
        models_dir: Path to your models. If not provided, and
            library_dir is not a S3 path, it is set to
            library_dir/models.
        aws_endpoint: S3 endpoint URL, use 'AWS' if not provided.
        aws_region: S3 region name, not always required for private storages.
        aws_access_key: S3 AWS access key.
        aws_secret_key: S3 AWS secret key.
        host: App host.
        port: App port.
        pixano_inference_url: Pixano inference URL.
    """
    App(
        library_dir,
        media_dir,
        models_dir,
        aws_endpoint,
        aws_region,
        aws_access_key,
        aws_secret_key,
        host,
        port,
        pixano_inference_url if pixano_inference_url != "" else None,
    )


if __name__ == "__main__":
    main()
