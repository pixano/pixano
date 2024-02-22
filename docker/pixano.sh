#!/bin/bash
 
echo "Pixano - Run Docker image"

# Check if there is path arg
if [ $# -eq 0 ]; then
    echo "Usage: $0 <library_directory>"
    exit 1
fi
# convert to absolute path, required by docker run
absolute_library_path=$(readlink -f "$1")

# get pixano versions from cli or default
pixano_ver=$2
if [ -z "$pixano_ver" ]
then
pixano_ver=0.5.0b4
fi
echo "pixano version: " $pixano_ver

# Pixano image name
pixano_image=pixano/pixano:$pixano_ver

# Check if image exist locally
if ! docker inspect "$pixano_image" &>/dev/null; then
    echo "Pixano Docker image is not present on your system, will pull it"
    docker pull "$pixano_image"
fi

docker run -v $absolute_library_path:/library -p 28005:28005 -t pixano/pixano:$pixano_ver