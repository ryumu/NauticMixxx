#!/usr/bin/env python3
"""Stable development launcher and publication after successful Linux builds."""
from pathlib import Path
import json
import os
import platform
import runpy
import shlex
import sys

from launch import atomic_write, desktop_entry


def state_path(project: Path) -> Path:
    return project / 'build/desktop' / f'latest-{platform.machine()}.json'


def register_build(project: Path, work: Path) -> None:
    prefix = work.resolve() / 'stage'
    for relative in ('bin/nauticmixxx', 'libexec/nauticmixxx/NauticMixxx',
                     'share/mixxx/controllers'):
        if not (prefix / relative).exists():
            raise ValueError(f'Incomplete Linux stage: {prefix / relative}')
    atomic_write(state_path(project), (json.dumps({'prefix': str(prefix)}) + '\n').encode())


def latest_prefix(project: Path) -> Path:
    prefix = Path(json.loads(state_path(project).read_text())['prefix'])
    if not (prefix / 'bin/nauticmixxx').is_file():
        raise ValueError(f'Latest Linux build is missing: {prefix}')
    return prefix


def publish_build(project: Path, work: Path) -> None:
    work = work.resolve()
    prefix = work / 'stage'
    # The first full build installs upstream resources after compilation/tests.
    # Until then, keep the previous desktop build registered.
    if not (prefix / 'share/mixxx/controllers').is_dir():
        print('Desktop publication deferred until the initial Linux install.')
        return
    binary = work / 'native/mixxx'
    atomic_write(prefix / 'bin/mixxx', binary.read_bytes(), binary.stat().st_mode & 0o777)
    stage = runpy.run_path(str(project / 'packaging/linux/stage-package.py'))['stage']
    stage(prefix, work / 'mixxx-2.5.6', project)
    register_build(project, work)
    print(f'Desktop build updated: {prefix}')


def desktop_directory() -> Path:
    home = Path.home()
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config')))
    settings = config / 'user-dirs.dirs'
    if settings.is_file():
        for line in settings.read_text().splitlines():
            if line.startswith('XDG_DESKTOP_DIR='):
                values = shlex.split(line.split('=', 1)[1])
                if values:
                    path = Path(values[0].replace('${HOME}', str(home)).replace('$HOME', str(home)))
                    if path.is_absolute():
                        return path
    return home / 'Desktop'


def install_desktop(project: Path) -> None:
    prefix = latest_prefix(project)
    contents = desktop_entry(prefix, project / 'packaging/linux/desktop.py',
                             project / 'branding/iCon-macOS-Dark-1024x1024@1x.png').encode()
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
    atomic_write(data / 'applications/org.nauticsoftware.NauticMixxx.desktop', contents)
    atomic_write(desktop_directory() / 'NauticMixxx.desktop', contents, 0o755)


def main() -> None:
    project = Path(__file__).resolve().parents[2]
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == '--publish-build':
        publish_build(project, Path(args[1]))
    elif len(args) == 2 and args[0] == '--register-build':
        register_build(project, Path(args[1]))
    elif args == ['--install-desktop']:
        install_desktop(project)
    else:
        launcher = latest_prefix(project) / 'bin/nauticmixxx'
        os.execv(str(launcher), [str(launcher), *args])


if __name__ == '__main__':
    main()
