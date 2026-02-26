# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import asyncio
import warnings
from functools import lru_cache

import fastapi
import pkg_resources  # type: ignore[import-untyped]
import uvicorn
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pixano.app.display import display_cli, display_colab, display_ipython
from pixano.app.main import create_app
from pixano.app.routers import API_PREFIXES
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
NON_SPA_PREFIXES = (
    *API_PREFIXES,
    "/_app",
    "/media",
    "/app_models",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
)

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
        data_dir: str = ".",
        *,
        library_dir: str | None = None,
        media_dir: str | None = None,
        models_dir: str | None = None,
        aws_endpoint: str | None = None,
        aws_region: str | None = None,
        aws_access_key: str | None = None,
        aws_secret_key: str | None = None,
        host: str = "127.0.0.1",
        port: int = 7492,
        pixano_inference_url: str | None = None,
    ):
        """Initialize and serve the Pixano app.

        Args:
            data_dir: Root data directory containing library/, media/,
                and models/ subdirectories.
            library_dir: Override for the library directory. If not
                provided, defaults to data_dir/library.
            media_dir: Override for the media directory. If not
                provided, defaults to data_dir/media.
            models_dir: Override for the models directory. If not
                provided, defaults to data_dir/models.
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
            inference_providers: dict = {}
            if pixano_inference_url is not None:
                from pixano.inference.providers.pixano_inference import PixanoInferenceProvider

                provider = PixanoInferenceProvider(url=pixano_inference_url)
                inference_providers[provider.name] = provider
            kwargs: dict = {
                "data_dir": data_dir,
                "aws_endpoint": aws_endpoint,
                "aws_region": aws_region,
                "aws_access_key": aws_access_key,
                "aws_secret_key": aws_secret_key,
                "inference_providers": inference_providers,
            }
            if inference_providers:
                kwargs["default_inference_provider"] = next(iter(inference_providers))
            if library_dir is not None:
                kwargs["library_dir"] = library_dir
            if media_dir is not None:
                kwargs["media_dir"] = media_dir
            if models_dir is not None:
                kwargs["models_dir"] = models_dir
            return Settings(**kwargs)

        # Create app
        settings = get_settings_override()
        templates = Jinja2Templates(directory=TEMPLATE_PATH)
        self.app = create_app(settings=settings)
        self.app.dependency_overrides[get_settings] = get_settings_override

        @self.app.get("/", response_class=HTMLResponse)
        def main_page(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        def _is_non_spa_path(path: str) -> bool:
            return any(path == prefix or path.startswith(f"{prefix}/") for prefix in NON_SPA_PREFIXES)

        try:
            self.app.mount("/_app", StaticFiles(directory=ASSETS_PATH), name="assets")
        # TODO: properly define environment variable for production to raise a RuntimeError accordingly
        except RuntimeError:
            warnings.warn(
                "Pixano app assets not found. If it is a production environment, this is not expected, "
                "check if you have built the assets for the UI."
            )

        @self.app.get("/{full_path:path}", include_in_schema=False)
        async def hash_spa_redirect(request: fastapi.Request, full_path: str):
            request_path = request.url.path
            if _is_non_spa_path(request_path):
                raise HTTPException(status_code=404, detail="Not Found")

            hash_url = f"/#/{full_path}" if full_path else "/"
            if request.url.query:
                hash_url = f"{hash_url}?{request.url.query}"
            return RedirectResponse(url=hash_url, status_code=307)

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


if __name__ == "__main__":
    from pixano.app.cli import main

    main()
