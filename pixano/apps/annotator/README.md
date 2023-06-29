<div align="center">

<picture>
    <img src="https://raw.githubusercontent.com/pixano/pixano/main/images/pixano_logo.png" alt="Pixano" height="100"/>
</picture>

<br/>

**Data-centric AI building blocks for computer vision applications**

***Under active development, subject to API change***

</div>


# Pixano Annotator

## Launching the Annotator from a terminal

You can start the Annotator with the following command:

```shell
pixano-annotator <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to browse the dataset.

## Launching the Annotator from a notebook

If you are using a notebook, you can start the Annotator by running a cell with:

```python
from pixano.apps import AnnotatorApp
annotator = AnnotatorApp(<path/to/your/datasets>)
```

You can then browse the Annotator directly from the notebook in another cell with:

```python
annotator.display()
```

## Browsing a dataset with the Annotator

From the Annotator homepage, you will be greeted with a list of all the Pixano format datasets found in the directory you provided.

Simply click on one of them to open it and you will be able to start annotating.
