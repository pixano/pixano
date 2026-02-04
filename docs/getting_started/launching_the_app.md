# Launching Pixano

## From a terminal: locally

You can start the Pixano app with the following command:

```shell
pixano server run your_data_dir/
```

This expects the data directory to contain `library/`, `media/`, and optionally `models/` subdirectories. You can override any of these with `--library-dir`, `--media-dir`, or `--models-dir`.

You will then be provided with a URL to open in your browser to use the app.

## From a terminal: S3 (Experimental)

Note that you can also connect to an S3 compatible storage by providing S3 paths as overrides for the library or media directory.

The following arguments have to be passed:

- `--library-dir`: S3 path to the library directory.
- `--models_dir`: Path to your models.
- `--aws_endpoint`: S3 endpoint URL, use 'AWS' if not provided.
- `--aws_region`: S3 region name, not always required for private storages.
- `--aws_access_key`: S3 AWS access key.
- `--aws_secret_key`: S3 AWS secret key.

So the command becomes:

```shell
pixano server run ./my_data \
--library-dir="s3://your_library_directory/" \
--models_dir="your_local_onnx_models/" \
--aws_endpoint="https://your-aws-endpoint.com" \
--aws_region="" \
--aws_access_key="your_access_key" \
--aws_secret_key="your_secret_key"
```

## From a notebook

If you are in a Jupyter or Google Colab notebook, you can start the app by running the following cells:

```python
from pixano.app import App
app = App("your_data_dir/")
```

You can then use the apps directly from the notebook in another cell with:

```python
app.display()
```

## From Docker

To launch the app you have to mount a data directory that contains `library/`, `media/`, and optionally `models/` subdirectories.

Here is an example:

```bash
docker run -d \
    --name pixano \
    -p 7492:7492 \
    -v ./my_data:/app/data \
    pixano/pixano:stable
```
