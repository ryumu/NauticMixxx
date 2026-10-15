#!/bin/sh
# Run on the Pi, as the ordinary development user.
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$#" -ne 0 ]; then
  printf 'Usage: %s (run on Raspberry Pi 5)\n' "$0" >&2
  exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
  printf 'Run as your ordinary user; dependency installation uses sudo.\n' >&2
  exit 1
fi
if ! command -v python3 >/dev/null; then
  printf 'Install Python 3 first: sudo apt-get install python3\n' >&2
  exit 1
fi
python3 "$project/scripts/check-raspberry-pi-dev.py" --platform-only
"$project/scripts/install-linux-build-deps.sh"
sudo apt-get install -y --no-install-recommends \
  patch gdb nodejs rsync tmux mesa-utils alsa-utils libinput-tools qt6-wayland
python3 "$project/scripts/check-raspberry-pi-dev.py"
printf '\nReady to build on the Pi:\n  RX3_BUILD_JOBS=1 RX3_BUILD_TYPE=RelWithDebInfo ./scripts/build-mixxx-rx3-linux.sh\n'
