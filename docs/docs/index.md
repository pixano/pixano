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


## Importing your datasets

Please refer to [this notebook](https://github.com/pixano/pixano/tree/main/notebooks/dataset/import_dataset.ipynb) for information on how to import your datasets.


## Using the Pixano Explorer

### Launching the Explorer from a terminal

You can start the Explorer with the following command:

```shell
pixano-explorer <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to browse the dataset.

### Launching the Explorer from a notebook

If you are using a notebook, you can run the Explorer in the background by running a cell like this:

```python
%%bash --bg
pixano-explorer <path/to/your/datasets>
```

You can then browse the explorer directly from notebook with this function:

```python
from pixano import notebook
notebook.display()
```

### Browsing a dataset with the Explorer

From the Explorer homepage, you will be greeted with a list of all the Pixano format datasets found in the directory you provided.

Simply click on one of them to open it and you will be able to see the dataset statistics if they have been computed, and browse the images from the list to check their annotations.


## Using the Pixano Annotator

*Coming soon...*


## Exporting your datasets

*Coming soon...*
