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

# The X11 libraries because opencv comes in through `pixano.schemas` and demands them at load
# time — a headless service that needs libxcb, which is a fair measure of what this import costs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The source of pixano, which the worker depends on. `hatch_build.py` and `README.md` are copied
# because the package build demands them, even when it is installed in editable mode.
COPY pyproject.toml uv.lock hatch_build.py README.md ./
COPY src/ ./src/

COPY packages/pixano-worker/ ./packages/pixano-worker/

# The installation is editable, so the worker reads this source at run time, and not as root. A
# copy keeps the modes of the checkout: under a strict umask (077) they would keep the user out.
RUN chmod -R a+rX /app

WORKDIR /app/packages/pixano-worker

# A single step, and the installation stays editable: `pixano` installs from a path, and its
# build hook would compile the frontend if it were forced non-editable — node and pnpm would
# then be needed in the image of a service that serves no page.
RUN uv sync --frozen --no-dev

ENV PATH="/app/packages/pixano-worker/.venv/bin:$PATH"

# The image does not run as root but as `pixano`, 1000:1000 unless the build says otherwise: the
# first account of most Linux machines, so that a folder this account bind-mounts is writable as
# it is. The two Dockerfiles of the application, in dockerfiles/, hold the same block.
ARG PIXANO_UID=1000
ARG PIXANO_GID=1000

# - A group that already holds this number (20, 100) is used as it is.
# - The data directories belong to the user: /data and /medias are where the compose stack
#   mounts them. A named volume takes the owner of the directory it is first mounted on; a bind
#   mount keeps the owner it has on the host.
# - The home is open like /tmp: a deployment may replace the user at run time (`--user`, `user:`
#   in a compose file, `runAsUser` in Kubernetes) by one that owns nothing in the image.
RUN (getent group "${PIXANO_GID}" > /dev/null || groupadd --gid "${PIXANO_GID}" pixano) \
    && useradd --no-log-init --uid "${PIXANO_UID}" --gid "${PIXANO_GID}" \
        --home-dir /home/pixano --no-create-home --shell /usr/sbin/nologin pixano \
    && install -d -m 1777 -o "${PIXANO_UID}" -g "${PIXANO_GID}" /home/pixano \
    && install -d -o "${PIXANO_UID}" -g "${PIXANO_GID}" /data /medias

# Set here and not above: the installation ran as root and must leave nothing in this home. It is
# the working directory too, so that the worker runs in a directory it may write to. The heartbeat
# of the liveness probe needs nothing: it goes to /tmp, which any user writes to.
ENV HOME=/home/pixano
WORKDIR /home/pixano

# By number: Kubernetes cannot check that a user given by name is not root (`runAsNonRoot`).
USER ${PIXANO_UID}:${PIXANO_GID}

CMD ["pixano-worker"]
