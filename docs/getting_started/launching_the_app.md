# Launching Pixano

## From a terminal: locally

You can start the Pixano app with the following command:

```shell
pixano server run your_data_dir/
```

This expects the data directory to contain `library/`, `media/`, and optionally `models/` subdirectories. Use `pixano init` to create this structure automatically (see the [Quickstart](quickstart.md)).

You will then be provided with a URL to open in your browser to use the app.

## From a terminal: S3 (Experimental)

You can connect to an S3-compatible storage by providing S3 paths and credentials as options:

- `--aws-endpoint`: S3 endpoint URL, use 'AWS' if not provided.
- `--aws-region`: S3 region name, not always required for private storages.
- `--aws-access-key`: S3 AWS access key.
- `--aws-secret-key`: S3 AWS secret key.

So the command becomes:

```shell
pixano server run ./my_data \
--aws-endpoint="https://your-aws-endpoint.com" \
--aws-region="" \
--aws-access-key="your_access_key" \
--aws-secret-key="your_secret_key"
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
