# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import typer

from pixano.cli.data import data_app
from pixano.cli.init import init as init_command
from pixano.cli.server import server_app


app = typer.Typer(no_args_is_help=True, help="Pixano CLI")
app.add_typer(server_app, name="server")
app.add_typer(data_app, name="dataset")
app.add_typer(data_app, name="data")
app.command(name="init")(init_command)


def main() -> None:
    """Entry point for the ``pixano`` console script."""
    app()
