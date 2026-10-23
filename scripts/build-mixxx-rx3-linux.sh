#!/bin/sh
# Native Linux build. Does not use macOS/Windows dependencies or cross compilation.
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=$(cat "$project/VERSION")
pi_profile=${RX3_PI_PROFILE:-off}
pi_lto=${RX3_PI_LTO:-OFF}
case "$pi_profile" in off|pi4|pi5) ;; *) printf 'RX3_PI_PROFILE must be off, pi4 or pi5.\n' >&2; exit 1 ;; esac
case "$pi_lto" in ON|OFF) ;; *) printf 'RX3_PI_LTO must be ON or OFF.\n' >&2; exit 1 ;; esac
suffix=
if [ "$pi_profile" != off ]; then
  suffix="-$pi_profile"
  if [ "$(uname -s)/$(uname -m)" != Linux/aarch64 ]; then
    printf 'Pi optimization profiles require native 64-bit ARM Linux.\n' >&2; exit 1
  fi
elif [ "$pi_lto" = ON ]; then
  printf 'RX3_PI_LTO requires a Pi optimization profile.\n' >&2; exit 1
fi
work=${RX3_BUILD_ROOT:-"$project/build/test-candidate/$version-linux-$(uname -m)$suffix"}
jobs=${RX3_BUILD_JOBS:-1}
tests=${RX3_BUILD_TESTING:-ON}
build_type=${RX3_BUILD_TYPE:-Release}
case "$(uname -s)/$(uname -m)" in
  Linux/aarch64|Linux/x86_64) ;;
  *) printf 'Use 64-bit Linux (aarch64 or x86_64). See docs/LINUX-RASPBERRY-PI.md.\n' >&2; exit 1 ;;
esac
if [ "$(getconf LONG_BIT)" != 64 ]; then
  printf 'A 64-bit kernel alone is insufficient; install a 64-bit userland.\n' >&2; exit 1
fi
case "$jobs" in ''|*[!0-9]*|0) printf 'RX3_BUILD_JOBS must be a positive integer.\n' >&2; exit 1 ;; esac
case "$tests" in ON|OFF) ;; *) printf 'RX3_BUILD_TESTING must be ON or OFF.\n' >&2; exit 1 ;; esac
case "$build_type" in Release|RelWithDebInfo|Debug) ;; *) printf 'RX3_BUILD_TYPE must be Release, RelWithDebInfo or Debug.\n' >&2; exit 1 ;; esac
if [ -f "$work/native/CMakeCache.txt" ]; then
  cached_profile=$(sed -n 's/^NAUTIC_PI_PROFILE:STRING=//p' "$work/native/CMakeCache.txt")
  if [ "${cached_profile:-off}" != "$pi_profile" ]; then
    printf 'Build root has a different CPU profile; choose a fresh RX3_BUILD_ROOT.\n' >&2; exit 1
  fi
fi
mkdir -p "$work"
work=$(CDPATH= cd -- "$work" && pwd)
archive="$work/mixxx-2.5.6.tar.gz"
if [ ! -f "$archive" ]; then
  curl --fail --location --retry 3 https://github.com/mixxxdj/mixxx/archive/refs/tags/2.5.6.tar.gz -o "$archive"
fi
printf '%s  %s\n' 9cfc9025d50d2511767ee52a07b8854f75c581f0585197d043bc219fcf9f9050 "$archive" | sha256sum -c -
source_tree="$work/mixxx-2.5.6"
digest=$(cat "$project"/patches/00[0-9][0-9]-*.patch | sha256sum | cut -d ' ' -f 1)
if [ ! -d "$source_tree" ]; then tar -xzf "$archive" -C "$work"; fi
marker="$source_tree/.rx3-patched"
if [ ! -f "$marker" ]; then
  for patch in "$project"/patches/00[0-9][0-9]-*.patch; do
    (cd "$source_tree" && GIT_CEILING_DIRECTORIES="$work" git apply --no-index "$patch")
  done
  printf '%s\n' "$digest" > "$marker"
fi
if [ "$(cat "$marker")" != "$digest" ] || [ ! -f "$source_tree/src/test/trackcapabilitypolicy_test.cpp" ]; then
  printf 'Source patches changed; choose a fresh RX3_BUILD_ROOT.\n' >&2; exit 1
fi
# Branding must be applied before Qt compiles its resource collection.
python3 "$project/packaging/linux/prepare-branding.py" "$source_tree" "$project"
cmake -S "$source_tree" -B "$work/native" -G Ninja \
  -DCMAKE_BUILD_TYPE="$build_type" -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DCMAKE_PROJECT_INCLUDE="$project/packaging/linux/desktop-build.cmake" \
  -DNAUTICMIX_VERSION="$(cat "$project/VERSION")" \
  -DCMAKE_INSTALL_PREFIX="$work/stage" -DCMAKE_INSTALL_LIBDIR=lib \
  -DQT6=ON -DQML=OFF -DOPTIMIZE=portable -DENGINEPRIME=OFF -DKEYFINDER=OFF \
  -DNAUTIC_PI_PROFILE="$pi_profile" -DNAUTIC_PI_LTO="$pi_lto" \
  -DBUILD_LOW_MEMORY=ON -DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON \
  -DBUILD_TESTING="$tests" -DBUILD_BENCH=OFF
cmake --build "$work/native" --target mixxx --parallel "$jobs"
if [ "$tests" = ON ]; then
  cmake --build "$work/native" --target mixxx-test --parallel "$jobs"
  (cd "$source_tree" && QT_QPA_PLATFORM=offscreen NAUTIC_SKIN_DIR="$project/skins/XDJ_RX3_Mixxx" NAUTIC_RX3_STYLESHEET="$project/skins/XDJ_RX3_Mixxx/style.qss" "$work/native/mixxx-test" \
    --gtest_filter='StartupUpdateCheckerTest.*:StartupUpdateDialogTest.*:StreamCompletionTest.*:LibraryTableViewStateTest.*:Rx3*:Rekordbox*:TrackCapabilityPolicyTest.*' \
    --gtest_output="xml:$work/rx3-tests.xml")
fi
cmake --install "$work/native"
python3 "$project/packaging/linux/stage-package.py" "$work/stage" "$source_tree" "$project"
python3 "$project/packaging/linux/desktop.py" --register-build "$work"
printf '\nBuilt NauticMixxx for %s. Start from a desktop session:\n  "%s/stage/bin/nauticmixxx"\n' "$(uname -m)" "$work"
