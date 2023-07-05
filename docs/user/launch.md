# Launching an app

## From a terminal

You can start the Explorer or Annotator app with the following command:

```shell
pixano-explorer <path/to/your/datasets>
```

```shell
pixano-annotator <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to use the app.

## From a notebook

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