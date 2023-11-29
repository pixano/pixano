<div align="center">

<img src="https://raw.githubusercontent.com/pixano/pixano/main/docs/assets/pixano_wide.png" alt="Pixano" height="100"/>

<br/>
<br/>

**Data-centric AI building blocks for computer vision applications**

**_Under active development, subject to API change_**

[![GitHub version](https://img.shields.io/github/v/release/pixano/pixano?label=release&logo=github)](https://github.com/pixano/pixano/releases)
[![PyPI version](https://img.shields.io/pypi/v/pixano?color=blue&label=release&logo=pypi&logoColor=white)](https://pypi.org/project/pixano/)
[![Documentation](https://img.shields.io/website/https/pixano.github.io?up_message=online&up_color=green&down_message=offline&down_color=orange&label=docs)](https://pixano.github.io)
[![License](https://img.shields.io/badge/license-CeCILL--C-green.svg)](LICENSE)
[![Python version](https://img.shields.io/pypi/pyversions/pixano?color=important&logo=python&logoColor=white)](https://www.python.org/downloads/)

</div>

<hr />

Pixano is an open-source tool by CEA List for exploring and annotating your dataset using AI features:

- **Fast dataset navigation** using the the modern storage format _Lance_
- **Multi-view datasets** support for images, and soon for _3D point clouds_ and _videos_
- **Import and export** support for dataset formats like _COCO_
- **Semantic search** using models like _CLIP_
- **Smart segmentation** using models like _SAM_

# Getting started

## Installing Pixano

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

## Using your datasets

Please refer to our Jupyter notebooks for <a href="https://github.com/pixano/pixano/blob/main/notebooks/datasets/import_dataset.ipynb" target="_blank">importing</a> and <a href="https://github.com/pixano/pixano/blob/main/notebooks/datasets/export_dataset.ipynb" target="_blank">exporting</a> your datasets.

## Using the Pixano apps

Please refer to these links for using the <a href="https://github.com/pixano/pixano/tree/main/pixano/apps/explorer/README.md" target="_blank">Pixano Explorer</a> and the <a href="https://github.com/pixano/pixano/tree/main/pixano/apps/annotator/README.md" target="_blank">Pixano Annotator</a> apps.

# Contributing

Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) for information on running Pixano locally and guidelines on how to publish your contributions.

# License

Pixano is licensed under the [CeCILL-C license](LICENSE).
