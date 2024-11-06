# Launching Pixano

## From a terminal: locally

You can start the Pixano app with the following command:

```shell
pixano your_library_directory/ your_media_directory/
```

You will then be provided with a URL to open in your browser to use the app.


## From a terminal: S3 (Experimental)
Note that you can also connect to an S3 compatible storage by providing an S3 path instead of a local path to your library of datasets.

The following arguments have to be passed:

- `--models_dir`: Path to your models.
- `--aws_endpoint`: S3 endpoint URL, use 'AWS' if not provided.
- `--aws_region`: S3 region name, not always required for private storages.
- `--aws_access_key`: S3 AWS access key.
- `--aws_secret_key`: S3 AWS secret key.

So the command becomes:

```shell
pixano s3://your_library_directory/ s3://your_media_directory/ \
--models_dir="your_local_onnx_models/"
--aws_endpoint="https://your-aws-endpoint.com" \
--aws_region="" \
--aws_access_key="your_access_key" \
--aws_secret_key="your_secret_key" \
```

## From a notebook

If you are in a Jupyter or Google Colab notebook, you can start the app by running the following cells:

```python
from pixano.app import App
app = App("your_library_directory/", "your_media_directory")
```

You can then use the apps directly from the notebook in another cell with:

```python
app.display()
```

## From Docker

To launch the app you have to mount a library directory, a media directory and a model directory (if you want to use a model).

Here is an example:
```bash
docker run -d \
    --name pixano \
    -p 8000:8000 \
    -v ./library:/app/library \
    -v ./media:/app/media \
    -v ./models:/app/models \
    pixano/pixano:stable
```
