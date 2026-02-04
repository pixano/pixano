# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

# Use the official Node.js image
FROM node:23-slim AS base

# Install pnpm and build frontend
FROM base AS build

RUN npm i -g corepack@latest

RUN corepack enable
RUN corepack use pnpm@10.4.1

WORKDIR /app

COPY ui/ ./ui

WORKDIR /app/ui

# Install pnpm dependencies
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store pnpm fetch --frozen-lockfile
RUN --mount=type=cache,id=pnpm,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile
WORKDIR /app/ui/apps/pixano

# Build the Frontend
RUN pnpm build

# Use the official Python slim image
FROM python:3.12-slim

# Arguments
# DATA_DIR: path to the root data directory (contains library/, media/, models/). It should be mounted.
# USE_AWS: whether to use AWS S3. If true, the AWS credentials should be mounted.
ARG DATA_DIR=/app
ARG USE_AWS=false

# Environment variables from the arguments to be used in the container
ENV DATA_DIR=${DATA_DIR}
ENV USE_AWS=${USE_AWS}

# Environment variables
# PYTHONDONTWRITEBYTECODE: prevents Python from generating .pyc files in the container
# PYTHONUNBUFFERED: turns off buffering for easier container logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pixano/ ./pixano
COPY ["pyproject.toml", "uv.lock", "hatch_build.py", "README.md", "./"]

# Install dependencies
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
RUN if [ "$USE_AWS" = "true" ]; then \
    uv pip install --system awscli && \
    mkdir -p /root/.aws && \
    --mount=type=secret,id=aws,target=/root/.aws/credentials; \
    fi

# Install the package
RUN uv sync

# Expose ports
# 8000: FastAPI server
EXPOSE 8000

# Copy the build files to FastAPI static files
WORKDIR /app/pixano/app
COPY --from=build /app/pixano/app/dist ./dist/

# Clean up the build environment
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Run the server
# TODO: Improve the conditional statement to avoid the use of the shell if possible
CMD ["sh", "-c", "if [ \"$USE_AWS\" = \"true\" ]; then \
    pixano server run \"${DATA_DIR}\" \"--host\" \"0.0.0.0\" \"--port\" \"8000\" \
    \"--aws-endpoint\" \"$(aws configure get aws_endpoint)\" \
    \"--aws-region\" \"$(aws configure get region)\" \
    \"--aws-access-key\" \"$(aws configure get aws_access_key_id)\" \
    \"--aws-secret-key\" \"$(aws configure get aws_secret_access_key)\";\
    else \
    pixano server run \"${DATA_DIR}\" \"--host\" \"0.0.0.0\" \"--port\" \"8000\"; \
    fi"]
