#!/bin/bash
# this script install system dependencies for vectorizing and sets up conda

sudo apt-get update
sudo apt-get install -y build-essential python-dev libagg-dev libpotrace-dev pkg-config 
conda env create -n dev -f envs/dev.yaml
conda init