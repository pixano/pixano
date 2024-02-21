FROM python:3.10
ARG pixano_version
ARG pixano_inference_version

# GPU support
RUN apt-get update && apt-get install -y build-essential libgl1-mesa-glx && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
  && pip install pixano==$pixano_version

# pixano-inference is required for semantic search, but heavy, so if you don't need semantic search you can comment it
# RUN pip install pixano-inference@git+https://github.com/pixano/pixano-inference@$pixano_inference_version

COPY library library

# env vars
ENV LANCEDB_CONFIG_DIR="/tmp"

EXPOSE 28005

CMD ["pixano", "--host", "0.0.0.0", "--port", "28005", "library"]
