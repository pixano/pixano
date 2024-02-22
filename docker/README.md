# Pixano Docker

Two options are available to pull (or build) and launch Pixano Docker Image

- [Docker Desktop](https://www.docker.com/products/docker-desktop), available on Windows, Mac, Linux, for a more user-friendly experience.

- Command line (this documentation cover optionnal build of Pixano Docker Image only with command line)


## Docker Explore

### Pull Image

This only need to be done once, or each time you want to pull another version

- Open Docker Desktop, tab "Images"
- Search image "pixano", press PULL for "pixano/pixano:<version>" (choose last available version, or latest)

![docker explore search image](assets/search-image.png)

Pixano Docker image will be downloaded from DockerHub (~7Go)

### Run Image

- Open Docker Desktop

Note: If you have already succesfully run a Pixano image, you can run the Pixano Container again from "Containers" tab.

For the first run, or if you want to change some settings:
 - go to "Images" tab

![run pixano image](assets/run-image.png)

- Press the run button

In the popup, open the "Optional settings".

![settings](assets/settings.png)

- Enter "28005" in the Ports (Host port) field. You can choose any available port, just note that you will have to use this port in your browser instead of the default 28005 given in logs (As Pixano running in Docker container is not aware of the port mapping)

- Select your pixano library directory in "Volumes" field "Host path", and enter "/library" (don't forget the '/') in the "Container path".

- Press "RUN"

![logs: pixano instance link](assets/logs-pixano-link.png)

- Click on the link provided [http://0.0.0.0:28005](http://0.0.0.0:28005) to open Pixano in your browser

If you have choosen a different port, replace 28005 with your choosen port


Now, Pixano container can be stopped and run again with the same config from "Container" tab.

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

If you have not already a local Pixano Docker image (local build or previous pull from DockerHub), this script will pull it from DockerHub

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
