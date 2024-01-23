<div align="center">

<img src="https://raw.githubusercontent.com/pixano/pixano/main/docs/assets/pixano_wide.png" alt="Pixano" height="100"/>

<br/>
<br/>

**Data-centric AI building blocks for computer vision applications**

**_Under active development, subject to API change_**

</div>

## Launching the Pixano app

### From a terminal

You can start the Pixano app with the following command:

```shell
pixano <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to use the app.

### From a notebook

If you are in a Jupyter or Google Colab notebook, you can start the app by running a cell with:

```python
from pixano.app import App
app = App(<path/to/your/datasets>)
```

You can then use the app directly from the notebook in another cell with:

```python
app.display()
```

## Using the Pixano app

Please refer to our [user guide](https://pixano.github.io/user/app/) on our documentation website for more information on how to use it.
