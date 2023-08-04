<div align="center">

<img src="https://raw.githubusercontent.com/pixano/pixano/main/docs/assets/pixano_wide.png" alt="Pixano" height="100"/>

<br/>
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

If you are in a Jupyter or Google Colab notebook, you can start the Explorer app by running a cell with:

```python
from pixano.apps import Explorer
explorer = Explorer(<path/to/your/datasets>)
```

You can then use the app directly from the notebook in another cell with:

```python
explorer.display()
```

## Using the Explorer

Please refer to our [user guide for Pixano Explorer](https://pixano.github.io/user/explorer/) on our documentation website for more information on how to use it.