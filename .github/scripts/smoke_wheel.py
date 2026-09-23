# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Check an installed release wheel using only the active Python environment."""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from importlib import import_module
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen


def smoke_test(expected_version: str) -> None:
    """Initialize fresh data, start the installed app, and fetch its bundled UI."""
    installed = version("pixano")
    if installed != expected_version:
        raise RuntimeError(f"Expected Pixano {expected_version}, found {installed}.")

    # The standard wizard exposes Hub imports without requiring an extra.
    import_module("huggingface_hub")

    entrypoint = Path(sys.executable).parent / ("pixano.exe" if os.name == "nt" else "pixano")
    if not entrypoint.is_file():
        raise RuntimeError(f"The installed pixano console entry point is missing: {entrypoint}")
    cli = [str(entrypoint)]
    with tempfile.TemporaryDirectory(prefix="pixano-wheel-smoke-") as temporary:
        root = Path(temporary)
        data_dir = root / "data"
        subprocess.run([*cli, "--help"], cwd=root, check=True, capture_output=True)
        subprocess.run([*cli, "init", str(data_dir)], cwd=root, check=True)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        base = f"http://127.0.0.1:{port}"

        with tempfile.TemporaryFile(mode="w+") as log:
            process = subprocess.Popen(
                [*cli, "server", "run", str(data_dir), "--host", "127.0.0.1", "--port", str(port)],
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"Server exited with status {process.returncode}.")
                    try:
                        with urlopen(f"{base}/health", timeout=2) as response:
                            if json.load(response) != {"status": "ok"}:
                                raise RuntimeError("Unexpected health response.")
                        break
                    except (URLError, TimeoutError):
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Server did not become healthy within 60 seconds.") from None
                        time.sleep(0.2)

                with urlopen(base, timeout=10) as response:
                    if response.headers.get_content_type() != "text/html":
                        raise RuntimeError("The home page did not return HTML.")
                    html = response.read().decode("utf-8")
                asset = re.search(r'["\'](/_app/[^"\']+\.js)["\']', html)
                if asset is None:
                    raise RuntimeError("The home page contains no bundled JavaScript asset.")
                with urlopen(f"{base}{asset.group(1)}", timeout=10) as response:
                    if response.headers.get_content_type() not in ("text/javascript", "application/javascript"):
                        raise RuntimeError("The bundled asset did not return JavaScript.")
                    if not response.read():
                        raise RuntimeError("The bundled JavaScript asset is empty.")

                ui_root = Path(str(files("pixano").joinpath("api/dist")))
                ui_assets = sorted(path for path in ui_root.rglob("*") if path.is_file())
                content_types = {
                    ".css": {"text/css"},
                    ".ico": {"image/x-icon", "image/vnd.microsoft.icon"},
                    ".js": {"text/javascript", "application/javascript"},
                    ".json": {"application/json"},
                    ".png": {"image/png"},
                    ".txt": {"text/plain"},
                }
                for path in ui_assets:
                    relative = path.relative_to(ui_root).as_posix()
                    if relative == "index.html":
                        # The home page above is rendered through Jinja.
                        continue
                    asset_url = f"{base}/{quote(relative)}"
                    with urlopen(asset_url, timeout=10) as response:
                        if response.url != asset_url:
                            raise RuntimeError(f"Bundled UI asset redirects instead of serving its file: {relative}")
                        expected_types = content_types.get(path.suffix)
                        if expected_types and response.headers.get_content_type() not in expected_types:
                            raise RuntimeError(f"Incorrect content type for bundled UI asset: {relative}")
                        if response.read() != path.read_bytes():
                            raise RuntimeError(f"Served UI asset differs from the installed wheel: {relative}")
            except BaseException:
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    print(
        f"Pixano {installed}: installed CLI, initialization, health, home page, "
        f"and all {len(ui_assets) - 1} bundled UI assets passed."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", required=True)
    smoke_test(parser.parse_args().expected_version)
