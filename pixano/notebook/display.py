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

import html
import json

import IPython.display
import shortuuid


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


def display(url: str = "http://127.0.0.1", port: int = 8000, height: int = 1000):
    """Display a Pixano app inside an environment

    Args:
        url (str, optional): Pixano app URL. Defaults to "127.0.0.1".
        port (int, optional): Pixano app port. Defaults to 8000.
        height (int, optional): Frame height. Defaults to 1000.
    """

    # Select function based on environment
    f = {
        "colab": display_colab,
        "ipython": display_ipython,
        "none": display_cli,
    }[get_env()]

    # Display Pixano app
    f(url, port, height)


def display_colab(url: str, port: int, height: int):
    """Display a Pixano app inside a Google Colab

    Args:
        url (str): Pixano app URL
        port (int): Pixano app port
        height (int): Frame height
    """

    # Define frame template
    shell = """
        (async () => {
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
