# Install

## Python Environment

As Pixano requires specific versions for its dependencies, we recommend creating a new Python virtual environment to install it.

For example, with <a href="https://github.com/conda-forge/miniforge" target="_blank">miniforge</a>:

```bash
conda create -n pixano_env -y python~=3.12
conda activate pixano_env
```

Then, you can install the Pixano package inside that environment with pip:

```bash
pip install pixano
```

## Docker

Pixano is available on [Docker Hub](https://hub.docker.com/r/pixano/pixano). We suggest you to pull the stable version which is the last release:

```bash
docker pull pixano/pixano:stable
```
