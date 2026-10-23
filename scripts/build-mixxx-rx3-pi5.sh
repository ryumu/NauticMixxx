#!/bin/sh
# Cortex-A76 build: run on Pi 5, not Pi 4.
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export RX3_PI_PROFILE=pi5
exec "$project/scripts/build-mixxx-rx3-linux.sh" "$@"
