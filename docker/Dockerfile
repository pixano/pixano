FROM python:3.10
ARG pixano_version
ARG pixano_inference_version

# GPU support
RUN apt-get update && apt-get install -y build-essential libgl1-mesa-glx && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip \
  && if [ -z "$pixano_version" ] ; then \
       pip install pixano; \
     else \
       pip install pixano==$pixano_version; \
    fi

# pixano-inference is required for semantic search, but heavy, so if you don't need semantic search you can comment it
RUN if [ -z "$pixano_inference_version" ] ; then \
    pip install pixano-inference; \
  else \
    pip install pixano-inference==$pixano_inference_version; \
  fi

# port 80 is exposed by default, but Docker Desktop requires explicit EXPOSE to allow port mapping
EXPOSE 80

# env vars
ENV LANCEDB_CONFIG_DIR "/tmp"

CMD ["pixano", "--host", "0.0.0.0", "--port", "80", "library"]
