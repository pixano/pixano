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

# Environment variables
# LIBRARY_DIR: path to the directory containing the Pixano datasets. It should be mounted as a volume.
# PYTHONDONTWRITEBYTECODE: prevents Python from generating .pyc files in the container
# PYTHONUNBUFFERED: turns off buffering for easier container logging
ENV LIBRARY_DIR=/app/library
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pixano/ ./pixano
COPY ["pyproject.toml", "README.md", "./"]

# Install dependencies and the package
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y
RUN pip install --upgrade pip
RUN pip install -e .

WORKDIR /app/pixano

# Expose ports
# 8000: FastAPI server
EXPOSE 8000

# Copy the build files to FastAPI static files
COPY --from=build /app/pixano/app/dist ./app/dist/

# Run the server
CMD ["sh", "-c", "pixano ${LIBRARY_DIR} --host 0.0.0.0 --port 8000"]
