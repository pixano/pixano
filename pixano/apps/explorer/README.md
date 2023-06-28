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

If you are using a notebook, you can run the Explorer in the background by running a cell like this:

```python
%%bash --bg
pixano-explorer <path/to/your/datasets>
```

You can then browse the Explorer directly from notebook with this function:

```python
from pixano import notebook
notebook.display()
```

## Browsing a dataset with the Explorer

From the Explorer homepage, you will be greeted with a list of all the Pixano format datasets found in the directory you provided.

Simply click on one of them to open it and you will be able to see the dataset statistics if they have been computed, and browse the images from the list to check their annotations.
