# Launching the app

## From a terminal

You can start the Pixano app with the following commands:

```shell
pixano <path/to/your/datasets>
```

You will then be provided with a URL to open in your browser to use the app.

### With S3 compatible storage

You can connect to a S3 compatible storage, by providing a S3 path instead of local path to your datasets

The followings environ variables have to be set:

- AWS_ENDPOINT : S3 Compatible Storage endpoint
- AWS_ACCESS_KEY_ID : access key credentials
- AWS_SECRET_ACCESS_KEY : secret access credentials
- AWS_REGION (optionnal): S3 region if relevant
- LOCAL_MODEL_DIR: local path to model directory

## From a notebook

If you are in a Jupyter or Google Colab notebook, you can start the app by running the following cells:

```python
from pixano.app import App
app = App(<path/to/your/datasets>)
```

You can then use the apps directly from the notebook in another cell with:

```python
app.display()
```
