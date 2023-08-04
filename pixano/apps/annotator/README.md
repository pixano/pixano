<div align="center">

<img src="https://raw.githubusercontent.com/pixano/pixano/main/docs/assets/pixano_wide.png" alt="Pixano" height="100"/>

<br/>
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

If you are in a Jupyter or Google Colab notebook, you can start the Annotator app by running a cell with:

```python
from pixano.apps import Annotator
annotator = Annotator(<path/to/your/datasets>)
```

You can then use the app directly from the notebook in another cell with:

```python
annotator.display()
```

## Using the Annotator

Please refer to our [user guide for Pixano Annotator](https://pixano.github.io/user/annotator/) on our documentation website for more information on how to use it.