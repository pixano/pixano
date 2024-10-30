# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

# Use the official Node.js image
FROM node:18-slim AS base

# Install pnpm and build frontend
FROM base AS build

RUN corepack enable

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
# LIBRARY_DIR: path to the directory containing the Pixano datasets. It should be mounted.
# MEDIA_DIR: path to the directory containing the Pixano media files. It should be mounted.
# MODELS_DIR: path to the directory containing the models. It should be mounted.
# USE_AWS: whether to use AWS S3. If true, the AWS credentials should be mounted and at least one of LIBRARY_DIR, MEDIA_DIR should be S3 paths.
ARG LIBRARY_DIR=/app/library
ARG MEDIA_DIR=/app/media
ARG MODELS_DIR=/app/models
ARG USE_AWS=false

# Environment variables from the arguments to be used in the container
ENV LIBRARY_DIR=${LIBRARY_DIR}
ENV MEDIA_DIR=${MEDIA_DIR}
ENV MODELS_DIR=${MODELS_DIR}
ENV USE_AWS=${USE_AWS}

# Environment variables
# PYTHONDONTWRITEBYTECODE: prevents Python from generating .pyc files in the container
# PYTHONUNBUFFERED: turns off buffering for easier container logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pixano/ ./pixano
COPY ["pyproject.toml", "README.md", "./"]

# Install dependencies
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
RUN pip install --upgrade pip
RUN if [ "$USE_AWS" = "true" ]; then \
    pip install awscli && \
    mkdir -p /root/.aws && \
    --mount=type=secret,id=aws,target=/root/.aws/credentials; \
    fi

# Install the package
RUN pip install -e .
RUN pip list

# Expose ports
# 8000: FastAPI server
EXPOSE 8000

# Copy the build files to FastAPI static files
WORKDIR /app/pixano/app
COPY --from=build /app/pixano/app/dist ./dist/

# Run the server
# TODO: Improve the conditional statement to avoid the use of the shell if possible
CMD ["sh", "-c", "if [ \"$USE_AWS\" = \"true\" ]; then \
    pixano \"${LIBRARY_DIR}\" \"${MEDIA_DIR}\" \"--models_dir\" \"${MODELS_DIR}\" \"--host\" \"0.0.0.0\" \"--port\" \"8000\" \
    \"--aws-endpoint\" \"$(aws configure get aws_endpoint)\" \
    \"--aws-region\" \"$(aws configure get region)\" \
    \"--aws-access-key\" \"$(aws configure get aws_access_key_id)\" \
    \"--aws-secret-key\" \"$(aws configure get aws_secret_access_key)\";\
    else \
    pixano \"${LIBRARY_DIR}\" \"${MEDIA_DIR}\" \"--models_dir\" \"${MODELS_DIR}\" \"--host\" \"0.0.0.0\" \"--port\" \"8000\"; \
    fi"]
