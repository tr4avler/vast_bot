#!/bin/bash

# Replace these variables with your desired values if needed
INSTANCE_ID="$1"
DEFAULT_IMAGE="nvidia/cuda:12.0.1-devel-ubuntu20.04"  # Default image
DEFAULT_DISK_SIZE="3"  # Default disk size in GB

# Use default values if they are not provided as arguments
CUSTOM_IMAGE=${2:-$DEFAULT_IMAGE}
DISK_SIZE=${3:-$DEFAULT_DISK_SIZE}

# Run the vastai command to create an instance with custom settings
vastai create instance "$INSTANCE_ID" --image "$CUSTOM_IMAGE" --disk "$DISK_SIZE"
