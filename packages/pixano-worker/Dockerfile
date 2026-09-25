# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

# The build context is the repository root, not this folder: the worker depends on `pixano`
# by path, and a context reduced to the package cannot see that source.
#
#   docker build -f packages/pixano-worker/Dockerfile .

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# `git` because `pixano-inference-client` is not published on PyPI and comes from a git repository.
# The X11 libraries because opencv comes in through `pixano.schemas` and demands them at load
# time — a headless service that needs libxcb, which is a fair measure of what this import costs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The source of pixano, which the worker depends on. `hatch_build.py` and `README.md` are copied
# because the package build demands them, even when it is installed in editable mode.
COPY pyproject.toml uv.lock hatch_build.py README.md ./
COPY src/ ./src/

COPY packages/pixano-worker/ ./packages/pixano-worker/
WORKDIR /app/packages/pixano-worker

# A single step, and the installation stays editable: `pixano` installs from a path, and its
# build hook would compile the frontend if it were forced non-editable — node and pnpm would
# then be needed in the image of a service that serves no page.
RUN uv sync --frozen --no-dev

ENV PATH="/app/packages/pixano-worker/.venv/bin:$PATH"
CMD ["pixano-worker"]
