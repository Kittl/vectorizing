#!/bin/bash
# Install the system dependencies required by the production image and devcontainer.

set -euo pipefail

if [[ "$(id -u)" -eq 0 ]]; then
  APT_GET=(apt-get)
else
  APT_GET=(sudo apt-get)
fi

"${APT_GET[@]}" update
"${APT_GET[@]}" install -y --no-install-recommends \
  wget \
  build-essential \
  python3-dev \
  libagg-dev \
  libpotrace-dev \
  pkg-config \
  libgl1 \
  libcairo2
