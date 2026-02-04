# Installation

## pip (recommended)

We recommend installing Pixano in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install pixano
```

## Docker

Pixano is available on [Docker Hub](https://hub.docker.com/r/pixano/pixano). Pull the stable version (latest release):

```bash
docker pull pixano/pixano:stable
```

See [Launching the app](launching_the_app.md#from-docker) for how to run the container.

## From source

Clone the repository and install with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/pixano/pixano.git
cd pixano
uv sync
```

When running from source, prefix every command with `uv run` (e.g. `uv run pixano server run ./my_data`).
