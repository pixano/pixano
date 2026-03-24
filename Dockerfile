# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

# Stage 1: Build the wheel (hatch_build.py hook handles the frontend build)
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_23.x | bash - && \
    apt-get install -y nodejs && \
    npm i -g corepack@latest && corepack enable && corepack use pnpm@10.4.1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY src/ ./src/
COPY ui/ ./ui/
COPY pyproject.toml uv.lock hatch_build.py README.md ./

RUN uv build --wheel

# Stage 2: Runtime (install the wheel and system dependencies)
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y ffmpeg libsm6 libxext6 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/dist/pixano-*.whl /tmp/
RUN uv pip install --system /tmp/pixano-*.whl && rm /tmp/pixano-*.whl

ARG DATA_DIR=/app/data
ENV DATA_DIR=${DATA_DIR}

EXPOSE 7492

CMD ["sh", "-c", "pixano init \"${DATA_DIR}\" && pixano server run \"${DATA_DIR}\" --host 0.0.0.0 --port 7492"]
