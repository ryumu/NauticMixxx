#!/bin/sh
# Cortex-A72 baseline: the resulting app also runs on Pi 5 with a compatible OS.
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export RX3_PI_PROFILE=pi4
exec "$project/scripts/build-mixxx-rx3-linux.sh" "$@"
