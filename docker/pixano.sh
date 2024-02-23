#!/bin/bash
 
# Check if there is path arg
if [ $# -eq 0 ]; then
    echo "Usage: $0 <library_directory>"
    exit 1
fi
# convert to absolute path, required by docker run
absolute_library_path=$(readlink -f "$1")

# get pixano image tag from cli or default
tag=$2
if [ -z "$tag" ]
then
tag=0.5.0b4
fi

# get custom host port
port=$3
if [ -z "$port" ]
then
port=80
fi

# Pixano image name
pixano_image=pixano/pixano:$tag
echo "Pixano - Run Docker image ("$pixano_image")"

# Check if image exist locally
if ! docker inspect "$pixano_image" &>/dev/null; then
    echo "Pixano Docker image is not present on your system, will pull it"
    docker pull "$pixano_image"
fi

echo -e "Acces Pixano on \033[1mhttp://0.0.0.0:"${port}"\033[0m"

docker run -v $absolute_library_path:/library -p $port:80 -t "$pixano_image"
