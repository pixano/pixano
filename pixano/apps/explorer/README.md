<div align="center">

<picture>
    <img src="https://raw.githubusercontent.com/pixano/pixano/main/images/pixano_logo.png" alt="Pixano" height="100"/>
</picture>

<br/>

**Data-centric AI building blocks for computer vision applications**

***Under active development, subject to API change***

</div>


# Pixano Explorer

## Launching the Explorer from a terminal

You can start the Explorer with the following command:

```shell
pixano-explorer <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to browse the dataset.

## Launching the Explorer from a notebook

If you are using a notebook, you can start the Explorer by running a cell with:

```python
from pixano.apps import ExplorerApp
explorer = ExplorerApp(<path/to/your/datasets>)
```

You can then browse the Explorer directly from the notebook in another cell with:

```python
explorer.display()
```

## Browsing a dataset with the Explorer

From the Explorer homepage, you will be greeted with a list of all the Pixano format datasets found in the directory you provided.

Simply click on one of them to open it and you will be able to see the dataset statistics if they have been computed, and browse the images from the list to check their annotations.
