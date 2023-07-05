# Getting started with Pixano


## Installing Pixano

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


## Importing and exporting your datasets

Please refer to the [import notebook](https://github.com/pixano/pixano/tree/main/notebooks/dataset/import_dataset.ipynb) and the [export notebook](https://github.com/pixano/pixano/tree/main/notebooks/dataset/export_dataset.ipynb) for information on how to import and export your datasets.

## Launching a Pixano App

### From a terminal

You can start the Explorer or Annotator app with the following command:

```shell
pixano-explorer <path/to/your/datasets>
```

```shell
pixano-annotator <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to use the app.

### From a notebook

If you are using a notebook, you can start the Explorer or Annotator app by running a cell with:

```python
from pixano.apps import ExplorerApp
explorer = ExplorerApp(<path/to/your/datasets>)
```

```python
from pixano.apps import AnnotatorApp
annotator = AnnotatorApp(<path/to/your/datasets>)
```

You can then use the app directly from the notebook in another cell with:

```python
explorer.display()
```

```python
annotator.display()
```

## Using a Pixano App

Please refer to the user guides for information on how to use the Pixano apps:

- [User guide for Pixano Explorer](user/explorer.md)
- [User guide for Pixano Annotator](user/annotator.md)


