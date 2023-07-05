<div align="center">

<picture>
    <img src="https://raw.githubusercontent.com/pixano/pixano/main/images/pixano_logo.png" alt="Pixano" height="100"/>
</picture>

<br/>

**Data-centric AI building blocks for computer vision applications**

***Under active development, subject to API change***

</div>


# Pixano Annotator

## Launching the Annotator

### From a terminal

You can start the Annotator app with the following command:

```shell
pixano-annotator <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to use the app.

### From a notebook

If you are using a notebook, you can start the Annotator app by running a cell with:

```python
from pixano.apps import AnnotatorApp
annotator = AnnotatorApp(<path/to/your/datasets>)
```

You can then use the app directly from the notebook in another cell with:

```python
annotator.display()
```

## Using the Annotator

Please refer to the [User guide for Pixano Annotator](../../../docs/docs/user/annotator.md) for more information on how to use it.