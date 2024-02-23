#!/bin/bash
 
echo "Pixano - Build Docker image"

# get pixano & pixano-inference versions from cli or default
pixano_version=$1
if [ -z "$pixano_version" ]
then
pixano_version=0.5.0b4
fi
echo "pixano version: " $pixano_version
pixano_ver=$2
if [ -z "$pixano_inference_version" ]
then
pixano_inference_version=v0.3.0b2
fi
echo "pixano-inference version: " $pixano_inference_version

tag=$3
if [ -z "$tag" ]
then
tag=$pixano_version
fi

sudo docker build -t pixano/pixano:$tag --build-arg pixano_version=$pixano_version --build-arg pixano_inference_version=$pixano_inference_version -f Dockerfile .

# uncomment to push image to DockerHub (restricted to owners of dockerHub pixano repositories)
# sudo docker push pixano/pixano:$tag
