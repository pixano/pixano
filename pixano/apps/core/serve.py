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

import asyncio
import html
import json
from pathlib import Path

import fastapi
import IPython.display
import shortuuid
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .main import Settings, create_app


def get_env() -> str:
    """Get current running environment

    Returns:
        str: Running environment
    """

    # If Google colab import succeeds
    try:
        import google.colab
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


def display_colab(url: str, port: int, height: int):
    """Display a Pixano app inside a Google Colab

    Args:
        url (str): Pixano app URL
        port (int): Pixano app port
        height (int): Frame height
    """

    # Define frame template
    shell = """
        (() => {
            const url = new URL(%URL%);
            const port = %PORT%;
            if (port) {
                url.port = port;
            }
            const iframe = document.createElement('iframe');
            iframe.src = url;
            iframe.setAttribute('width', '100%');
            iframe.setAttribute('height', '%HEIGHT%');
            iframe.setAttribute('frameborder', 0);
            document.body.appendChild(iframe);
        })();
    """

    # Replace variables in template
    replacements = [
        ("%HEIGHT%", "%d" % height),
        ("%PORT%", "%d" % port),
        ("%URL%", json.dumps(url)),
    ]
    for k, v in replacements:
        shell = shell.replace(k, v)

    # Display frame
    script = IPython.display.Javascript(shell)
    IPython.display.display(script)


def display_ipython(url: str, port: int, height: int):
    """Display a Pixano app inside a Jupyter notebook

    Args:
        url (str): Pixano app URL
        port (int): Pixano app port
        height (int): Frame height
    """

    # Define frame template
    shell = """
        <iframe id="%HTML_ID%" width="100%" height="%HEIGHT%" frameborder="0">
        </iframe>
        <script>
            (function() {
                const frame = document.getElementById(%JSON_ID%);
                const url = new URL(%URL%, window.location);
                const port = %PORT%;
                if (port) {
                    url.port = port;
                }
                frame.src = url;
            })();
        </script>
    """

    # Replace variables in template
    frame_id = f"frame-{shortuuid.uuid()}"
    replacements = [
        ("%HTML_ID%", html.escape(frame_id, quote=True)),
        ("%JSON_ID%", json.dumps(frame_id)),
        ("%HEIGHT%", "%d" % height),
        ("%PORT%", "%d" % port),
        ("%URL%", json.dumps(url)),
    ]
    for k, v in replacements:
        shell = shell.replace(k, v)

    # Display frame
    iframe = IPython.display.HTML(shell)
    IPython.display.display(iframe)


def display_cli(url: str, port: int, height: int):
    """Display a Pixano app inside a command line interface

    Args:
        url (str): Pixano app URL
        port (int): Pixano app port
        height (int): Frame height
    """

    print(f"Please visit {url}:{port} in a web browser.")


class PixanoApp:
    """Pixano App

    Attributes:
        config (uvicorn.Config): App config
        server (uvicorn.Server): App server
        task_function (typing.Callable): Run task function for running environment
        display_function (typing.Callable): Display function for running environment
    """

    def __init__(
        self,
        library_dir: str,
        assets_path: str,
        template_path: str,
        host: str = "127.0.0.1",
        port: int = 8000,
    ):
        """Initialize and run Pixano app

        Args:
            library_dir (str): Dataset library directory
            host (str, optional): App host. Defaults to "127.0.0.1".
            port (int, optional): App port. Defaults to 8000.
        """

        # Create app
        templates = Jinja2Templates(directory=template_path)
        settings = Settings(data_dir=Path(library_dir))
        app = create_app(settings)

        @app.get("/", response_class=HTMLResponse)
        def main(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        self.config = uvicorn.Config(app, host=host, port=port)
        self.server = uvicorn.Server(self.config)

        # Get environmennt
        self.task_function = {
            "colab": asyncio.get_event_loop().create_task,
            "ipython": asyncio.get_event_loop().create_task,
            "none": asyncio.run,
        }[get_env()]
        self.display_function = {
            "colab": display_colab,
            "ipython": display_ipython,
            "none": display_cli,
        }[get_env()]

        # Serve app
        self.task_function(self.server.serve())

    def display(self, height: int = 1000) -> None:
        """Display Pixano app

        Args:
            height (int, optional): Frame height. Defaults to 1000.
        """

        # Wait for app to be online
        while not self.server.started:
            self.task_function(asyncio.wait(0.1))

        # Display app
        for server in self.server.servers:
            for socket in server.sockets:
                address = socket.getsockname()
                self.display_function(
                    url=f"http://{address[0]}", port=address[1], height=height
                )
