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
pixano your_dataset_directory/
```

You will then be provided with a URL to open in your browser to use the app.

Note that you can also connect to an S3 compatible storage by providing an S3 path instead of a local path to your datasets.

The following arguments have to be passed:

- `--aws_endpoint`: S3 endpoint URL, use 'AWS' if not provided.
- `--aws_region`: S3 region name, not always required for private storages.
- `--aws_access_key`: S3 AWS access key.
- `--aws_secret_key`: S3 AWS secret key.
- `--local_model_dir`: Local path to your models.

So the command becomes:

```shell
pixano s3://your_dataset_directory/ \
--aws_endpoint="https://your-aws-endpoint.com" \
--aws_region="" \
--aws_access_key="your_access_key" \
--aws_secret_key="your_secret_key" \
--local_model_dir="your_local_onnx_models/"
```

### From a notebook

If you are in a Jupyter or Google Colab notebook, you can start the app by running a cell with:

```python
from pixano.app import App
app = App("your_dataset_directory/")
```

You can then use the app directly from the notebook in another cell with:

```python
app.display()
```

## Using the Pixano app

Please refer to our [user guide](https://pixano.github.io) on our documentation website for more information on how to use it.
