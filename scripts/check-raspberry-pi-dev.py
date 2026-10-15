#!/usr/bin/env python3
"""Read-only checks for the native Raspberry Pi 5 development environment."""
import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess


def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return result.stdout.strip() if result.returncode == 0 else ''


def platform_errors(system, machine, bits, architecture, model, release):
    errors = []
    if (system, machine, bits, architecture) != ('Linux', 'aarch64', 64, 'arm64'):
        errors.append('64-bit Linux kernel AND arm64 userland are required.')
    if not model.startswith('Raspberry Pi 5 Model'):
        errors.append('Run this setup on a Raspberry Pi 5, not the development PC.')
    # Raspberry Pi OS arm64 can identify itself as Debian rather than Raspbian.
    supported = (release.get('ID') in ('debian', 'raspbian')
                 and release.get('VERSION_CODENAME') in ('bookworm', 'trixie'))
    if not supported:
        errors.append('This Pi setup targets Raspberry Pi OS / Debian Bookworm or Trixie.')
    return errors


def version_at_least(value, minimum):
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', value)
    return bool(match and tuple(int(part or 0) for part in match.groups()) >= minimum)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform-only', action='store_true',
                        help='Check hardware and OS before installing dependencies')
    parser.add_argument('--build-root', type=Path,
                        default=Path(__file__).resolve().parents[1],
                        help='Existing directory on the build filesystem, for free-space reporting')
    args = parser.parse_args()
    if not args.build_root.is_dir():
        parser.error('--build-root must be an existing directory')
    model_path = Path('/proc/device-tree/model')
    model = model_path.read_text().rstrip('\x00\n') if model_path.exists() else 'unknown'
    release = platform.freedesktop_os_release() if platform.system() == 'Linux' else {}
    architecture = command('dpkg', '--print-architecture')
    bits = struct.calcsize('P') * 8
    print(f"Model: {model}\nOS: {release.get('PRETTY_NAME', 'unknown')}")
    print(f'Kernel: {platform.machine()}; userland: {bits}-bit / {architecture or "unknown"}')
    errors = platform_errors(platform.system(), platform.machine(), bits,
                             architecture, model, release)
    if not args.platform_only and not errors:
        for name in ('c++', 'cmake', 'ninja', 'pkg-config', 'git', 'curl', 'patch',
                     'gdb', 'node', 'rsync', 'tmux', 'glxinfo', 'aplay', 'libinput'):
            if not shutil.which(name):
                errors.append(f'Missing tool: {name}')
        cmake = command('cmake', '--version')
        qt = command('pkg-config', '--modversion', 'Qt6Core')
        print(f'CMake: {cmake.splitlines()[0] if cmake else "missing"}; Qt6Core: {qt or "missing"}')
        if not version_at_least(cmake, (3, 21, 0)):
            errors.append('CMake >= 3.21 is required by Mixxx 2.5.6.')
        if not version_at_least(qt, (6, 2, 0)):
            errors.append('Qt6Core development files >= 6.2 are required.')
        if command('python3', '-c', 'from PIL import Image; print("OK")') != 'OK':
            errors.append('Python Pillow is required for application branding.')
        session = os.environ.get('XDG_SESSION_TYPE', 'unknown')
        print(f'Desktop session: {session}')
        if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
            print('NOTE: No desktop in this shell; SSH builds are fine. Run GUI checks on the Pi desktop.')
        print('NOTE: CMake will check the complete audio/codec/Qt dependency set during configuration.')
    free_gib = shutil.disk_usage(args.build_root).free / (1024 ** 3)
    print(f'Free build space: {free_gib:.1f} GiB')
    if free_gib < 15:
        print('NOTE: Plan for 15 GiB or more of free space; actual build usage may vary.')
    meminfo = Path('/proc/meminfo')
    if meminfo.exists():
        for line in meminfo.read_text().splitlines():
            if line.startswith(('MemTotal:', 'MemAvailable:', 'SwapTotal:')):
                print(line)
    for error in errors:
        print(f'ERROR: {error}')
    if errors:
        return 1
    print('Platform check: OK' if args.platform_only else 'Development tools: OK; hardware GUI/audio validation pending.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
