#!/bin/bash
 
echo "Pixano - Creation image docker"

# get pixano & pixano-inference versions from cli or default
pixano_ver=$1
if [ -z "$pixano_ver" ]
then
pixano_ver=0.5.0b4
fi
echo "pixano version: " $pixano_ver
pixano_inference_ver=$2
if [ -z "$pixano_inference_ver" ]
then
pixano_inference_ver=v0.3.0b2
fi
echo "pixano-inference version: " $pixano_inference_ver

sudo docker build -t pixano/pixano:$pixano_ver --build-arg pixano_version=$pixano_ver --build-arg pixano_inference_version=$pixano_inference_ver -f Dockerfile .

# uncomment to push image to DockerHub (restricted to owners of dockerHub pixano repositories)
# sudo docker push pixano/pixano:$pixano_ver
