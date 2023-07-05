<div align="center">

<picture>
    <img src="https://raw.githubusercontent.com/pixano/pixano/main/images/pixano_logo.png" alt="Pixano" height="100"/>
</picture>

<br/>

**Data-centric AI building blocks for computer vision applications**

***Under active development, subject to API change***

</div>


# Pixano Explorer

## Launching the Explorer

### From a terminal

You can start the Explorer app with the following command:

```shell
pixano-explorer <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to use the app.

### From a notebook

If you are using a notebook, you can start the Explorer app by running a cell with:

```python
from pixano.apps import ExplorerApp
explorer = ExplorerApp(<path/to/your/datasets>)
```

You can then use the app directly from the notebook in another cell with:

```python
explorer.display()
```

## Using the Explorer

Please refer to the [User guide for Pixano Explorer](../../../docs/docs/user/explorer.md) for more information on how to use it.