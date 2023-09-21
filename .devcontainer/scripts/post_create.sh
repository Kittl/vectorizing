#!/bin/bash
# this script install system dependencies for vectorizing and sets up conda

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# install system dependencies
bash "$SCRIPT_DIR"/../../scripts/install_system_dependencies.sh

# setup conda
conda env create -n dev -f envs/dev.yaml
conda init