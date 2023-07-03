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
from pathlib import Path

import fastapi
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pixano import notebook

from .main import Settings, create_app


def _get_env() -> str:
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


class PixanoApp:
    def __init__(
        self,
        library_dir: str,
        assets_path: str,
        template_path: str,
        host: str = "127.0.0.1",
        port: int = 8000,
    ):
        """Run Pixano app

        Args:
            library_dir (str): Dataset library directory
            host (str, optional): App host. Defaults to "127.0.0.1".
            port (int, optional): App port. Defaults to 8000.
        """

        templates = Jinja2Templates(directory=template_path)
        settings = Settings(data_dir=Path(library_dir))
        app = create_app(settings)

        @app.get("/", response_class=HTMLResponse)
        def main(request: fastapi.Request):
            return templates.TemplateResponse("index.html", {"request": request})

        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
        self.config = uvicorn.Config(app, host=host, port=port)
        self.server = uvicorn.Server(self.config)

        self.env = {
            "colab": asyncio.get_event_loop().create_task,
            "ipython": asyncio.get_event_loop().create_task,
            "none": asyncio.run,
        }[_get_env()]

        self.env(self.server.serve())

    def display(self) -> None:
        """Display Pixano app"""

        while not self.server.started:
            self.env(asyncio.wait(0.1))

        for server in self.server.servers:
            for socket in server.sockets:
                address = socket.getsockname()
                notebook.display(url=f"http://{address[0]}", port=address[1])
