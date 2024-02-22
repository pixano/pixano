# Pixano Docker

## Docker Explore

For a more user-friendly experience, you can use [Docker Desktop](https://www.docker.com/products/docker-desktop), available on Windows, Mac, Linux

TODO: Docker Desktop build/run

## Command line

### Docker image Build

This is not required, as the run script will get Pixano docker image from DockerHub, if the desired Pixano image is not present on your system.

But if you want to build your own image with different versions of pixano and/or pixano-inference, you can do it with the "build.sh" script.

Run the build script:
```
./build.sh <pixano_version> <pixano-inference_version>
```

If you don't provide pixano and pixano-inference versions, defaults version specified in this script will be used

#### Side-note on image weight

You can generate a light-weight Pixano docker image (~2Go) without importing pixano-inference, but semantic search won't be available then.
Comment or uncomment the following line in Dockerfile

> RUN pip install pixano-inference@git+https://github.com/pixano/pixano-inference@$pixano_inference_version

With pixano-inference module, the image will be heavier (~12Go), because pixano-inference use some heavy libs (mainly pytorch)

### Docker image Run

Run the pixano script:
```
./pixano.sh <local_library_directory> <pixano_version>
```
pixano_version is optional, use default if not provided.

Then open your browser and go to [http://127.0.0.1:28005](http://127.0.0.1:28005)

Please note that your local library directory must contains a "models" directory with .onnx model(s) weights for interactive segmentation to work.

Refer to [Interactive annotation Notebook](https://github.com/pixano/pixano/blob/develop/notebooks/models/interactive_annotation.ipynb) for instructions on how to generate the .onnx model file for interactive segmentation.

#### S3 Storage

Pixano allows connection to a S3 compatible storage

*work in progress*

 TODO: runS3.sh

- Add AWS relevent environment vars in Dockerfile (for credentials, use docker "secret" (need to read about this))
- Add MODEL_DIR environment variable in Dockerfile (ENV MODEL_DIR=library/models)
- change CMD line "library" to "s3://*your_bucket*"
