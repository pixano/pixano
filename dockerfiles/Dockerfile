# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

FROM python:3.12-slim

ARG PIXANO_VERSION

ENV DATA_DIR=/library \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN test -n "$PIXANO_VERSION"

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libsm6 libxext6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "pixano==${PIXANO_VERSION}"

# The image does not run as root but as `pixano`, 1000:1000 unless the build says otherwise: the
# first account of most Linux machines, so that a folder this account bind-mounts is writable as
# it is. Dockerfile.source and the worker's Dockerfile hold the same block.
ARG PIXANO_UID=1000
ARG PIXANO_GID=1000

# - A group that already holds this number (20, 100) is used as it is.
# - The data directories belong to the user. /library is where `docker run` keeps the data by
#   default, /data and /medias are where the compose stack mounts them. A named volume takes the
#   owner of the directory it is first mounted on; a bind mount keeps the owner it has on the host.
# - The home is open like /tmp: a deployment may replace the user at run time (`--user`, `user:`
#   in a compose file, `runAsUser` in Kubernetes) by one that owns nothing in the image.
RUN (getent group "${PIXANO_GID}" > /dev/null || groupadd --gid "${PIXANO_GID}" pixano) \
    && useradd --no-log-init --uid "${PIXANO_UID}" --gid "${PIXANO_GID}" \
        --home-dir /home/pixano --no-create-home --shell /usr/sbin/nologin pixano \
    && install -d -m 1777 -o "${PIXANO_UID}" -g "${PIXANO_GID}" /home/pixano \
    && install -d -o "${PIXANO_UID}" -g "${PIXANO_GID}" "${DATA_DIR}" /data /medias

# Set here and not above: the installation ran as root and must leave nothing in this home, where
# the Hugging Face cache of a LeRobot import from the Hub goes. It is the working directory too,
# because DuckDB spills what does not fit in memory into the directory it runs in.
ENV HOME=/home/pixano
WORKDIR /home/pixano

# By number: Kubernetes cannot check that a user given by name is not root (`runAsNonRoot`).
USER ${PIXANO_UID}:${PIXANO_GID}

EXPOSE 7492

CMD ["sh", "-c", "pixano init \"${DATA_DIR}\" && pixano server run \"${DATA_DIR}\" --host 0.0.0.0 --port 7492"]
