<div align="center">

<img src="https://raw.githubusercontent.com/pixano/pixano/main/docs/assets/pixano_wide.png" alt="Pixano" height="100"/>

<br/>
<br/>

**Data-centric AI building blocks for computer vision applications**

**_Under active development, subject to API change_**

[![GitHub version](https://img.shields.io/github/v/release/pixano/pixano?label=release&logo=github)](https://github.com/pixano/pixano/releases)
[![PyPI version](https://img.shields.io/pypi/v/pixano?label=release&logo=pypi&logoColor=white)](https://pypi.org/project/pixano/)
[![Docker](https://img.shields.io/docker/v/pixano/pixano?sort=semver&label=release&logo=docker&logoColor=white)](https://hub.docker.com/r/pixano/pixano/)
[![Coverage](https://img.shields.io/codecov/c/github/pixano/pixano/main?logo=codecov&logoColor=white)](https://codecov.io/github/pixano/pixano)
[![Tests](https://img.shields.io/github/actions/workflow/status/pixano/pixano/backend.yml?label=tests&branch=main)](https://github.com/pixano/pixano/actions/workflows/backend.yml)
[![Documentation](https://img.shields.io/website?url=https%3A%2F%2Fpixano.github.io%2F&up_message=online&down_message=offline&label=docs)](https://pixano.github.io)
[![Python version](https://img.shields.io/pypi/pyversions/pixano?color=blue&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-CeCILL--C-blue.svg)](LICENSE)

</div>

<hr />

Pixano is an open-source tool by CEA List for exploring and annotating your dataset using AI features:

- **Fast dataset navigation** using the the modern storage format _Lance_
- **Multi-view datasets** support for _text_, _images_ and _videos_, and soon for _3D point clouds_
- **Import and export** support for dataset formats like _COCO_
- **Semantic search** using models like _CLIP_
- **Smart segmentation** using models like _SAM_

# Installing Pixano

As Pixano requires specific versions for its dependencies, we recommend creating a new Python virtual environment to install it.

For example, with <a href="https://conda.io/projects/conda/en/latest/user-guide/install/index.html" target="_blank">conda</a>:

```shell
conda create -n pixano_env python=3.10
conda activate pixano_env
```

Then, you can install the Pixano package inside that environment with pip:

```shell
pip install pixano
```

Pixano is also available on the [Docker Hub](https://hub.docker.com/r/pixano/pixano), you can also install it as follows:

```shell
docker pull pixano/pixano:stable
```

# Using Pixano

Please refer to our <a href="https://pixano.github.io/pixano/latest/getting_started/" target="_blank">Getting started</a> guide for information on how to launch and use the Pixano app, and how to create and use Pixano datasets.

# Contributing

Please refer to our [CONTRIBUTING.md](CONTRIBUTING.md) for information on running Pixano locally and guidelines on how to publish your contributions.

# License

Pixano is licensed under the [CeCILL-C license](LICENSE).
