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

EXPOSE 7492

CMD ["sh", "-c", "pixano init \"${DATA_DIR}\" && pixano server run \"${DATA_DIR}\" --host 0.0.0.0 --port 7492"]
