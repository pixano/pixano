<div align="center">

<picture>
    <img src="https://raw.githubusercontent.com/pixano/pixano/main/images/pixano_logo.png" alt="Pixano" height="100"/>
</picture>

<br/>
<br/>

**Data-centric AI building blocks for computer vision applications**

***Under active development, subject to API change***

[![License](https://img.shields.io/badge/license-CeCILL--C-green.svg)](LICENSE)
[![GitHub version](https://img.shields.io/github/v/release/pixano/pixano?label=release&logo=github)](https://github.com/pixano/pixano/releases)
[![PyPI version](https://img.shields.io/pypi/v/pixano?color=blue&label=release&logo=pypi&logoColor=white)](https://pypi.org/project/pixano/)
[![Python version](https://img.shields.io/pypi/pyversions/pixano?color=important&logo=python&logoColor=white)](https://www.python.org/downloads/)

</div>


# Installing Pixano

As Pixano requires specific versions for its dependencies, we recommend creating a new Python virtual environment to install it.

For example, with conda:

```shell
conda create -n pixano_env python=3.10
conda activate pixano_env
```

Then, you can install the Pixano package inside that environment with pip:

```shell
pip install pixano
```

# Using Pixano

- [Importing your datasets](notebooks/dataset/import_dataset.ipynb)
- [Using the Pixano Explorer](pixano/apps/explorer/README.md)
- [Using the Pixano Annotator](pixano/apps/annotator/README.md)
- [Exporting your datasets](notebooks/dataset/export_dataset.ipynb)

# Contributing

If you find a bug or you think of some missing features that could be useful while using Pixano, please [open an issue](https://github.com/pixano/pixano/issues)!

To contribute more actively to the project, you are welcome to develop the fix or the feature you have in mind, and [create a pull request](https://github.com/pixano/pixano/pulls)!

And if you want to change the application to your liking, feel free to [fork this repository](https://github.com/pixano/pixano/fork)!


# License

Pixano is licensed under the [CeCILL-C license](LICENSE).
