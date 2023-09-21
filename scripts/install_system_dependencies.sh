#!/bin/bash
# this script install system dependencies for vectorizing

sudo apt-get update
sudo apt-get install -y build-essential libagg-dev libpotrace-dev pkg-config libffi-dev libcairo2-dev
