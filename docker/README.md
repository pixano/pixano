# Pixano Docker

## Docker image Build

Just run the script:
```
./build.sh <pixano_version> <pixano-inference_version>
```

If you don't provide pixano and pixano-inference versions, defaults version specified in this script will be used


### Note On Dockerfile and image weight

You can generate a light-weight Pixano docker image (~2Go) without importing pixano-inference, but semantic search won't be available then.
Comment or uncomment the following line in Dockerfile

> RUN pip install pixano-inference@git+https://github.com/pixano/pixano-inference@$pixano_inference_version

With pixano-inference module, the image will be much heavier (~12Go), because pixano-inference use some heavy libs (mainly pytorch)

You can also change the default port (EXPOSE line and CMD line)

## Docker image Run

Run
```
docker -p 28005:28005 -t pixano/pixano:<pixano_version>
```

Then open your browser and go to [http://127.0.0.1:28005](http://127.0.0.1:28005)

## Add datasets

Run
```
docker container list | grep pixano
```
to find pixano container id.


You can copy a dataset in the Docker container, once started, with
```
docker cp <local_dataset_path> <pixano_container_id>:library
```

## S3 Storage

Instead of copying datasets, you can access to a S3 compatible storage

*work in progress*

- Add AWS relevent environment vars in Dockerfile (for credentials, use docker "secret" (need to read about this))
- Add MODEL_DIR environment variable in Dockerfile (ENV MODEL_DIR=library/models)
- change CMD line "library" to "s3://*your_bucket*"
