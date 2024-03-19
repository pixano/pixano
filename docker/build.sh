#!/bin/bash
 
echo "Pixano - Build Docker image"

# get pixano & pixano-inference versions from cli or default
if [ -n "$1" ]
then
pixano_version=$1
echo "pixano version: " $pixano_version
else
pixano_version=
fi
if [ -n "$2" ]
then
pixano_inference_version=$2
echo "pixano-inference version: " $pixano_inference_version
else
pixano_inference_version=
fi

if [ -n "$3" ]
then
tag=$3
else
tag=latest
fi

sudo docker build -t pixano/pixano:$tag --build-arg pixano_version=$pixano_version --build-arg pixano_inference_version=$pixano_inference_version -f Dockerfile .
