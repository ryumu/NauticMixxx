#!/usr/bin/env python3
"""Launch a relocatable Linux build with an isolated, English-first RX3 profile."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET


def atomic_write(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(data)
            os.fchmod(file.fileno(), mode)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def sync_controller_mappings(resources: Path, profile: Path) -> None:
    manifest = resources / 'nautic-controller-files.json'
    if not manifest.is_file():
        return
    for relative in json.loads(manifest.read_text()):
        name = Path(relative)
        if name.is_absolute() or '..' in name.parts:
            raise ValueError(f'Invalid bundled controller path: {relative}')
        source = resources / 'controllers' / name
        destination = profile / 'controllers' / name
        current = destination.read_bytes() if destination.exists() else None
        latest = source.read_bytes()
        if current == latest:
            continue
        if current is not None:
            digest = hashlib.sha256(current).hexdigest()
            backup = profile / 'controllers/.nautic-backups' / name.parent / f'{name.name}.{digest}.bak'
            if not backup.exists():
                atomic_write(backup, current)
        atomic_write(destination, latest, source.stat().st_mode & 0o777)


def seed_profile(resources: Path, profile: Path) -> None:
    # Only seed a new profile. Reopening the app must preserve users' choices.
    profile.mkdir(parents=True, exist_ok=True)
    config = profile / 'mixxx.cfg'
    if config.exists():
        sync_controller_mappings(resources, profile)
        return
    for relative in ('controllers', 'effects/chains'):
        shutil.copytree(resources / relative, profile / relative, dirs_exist_ok=True)
    root = ET.Element('Effects')
    presets = ET.SubElement(root, 'QuickEffectPresetList')
    for name in ('RX3 REVERB', 'RX3 PING PONG', 'RX3 NOISE', 'RX3 FILTER'):
        ET.SubElement(presets, 'ChainPresetName').text = name
    effects = profile / 'effects.xml'
    if not effects.exists():
        ET.ElementTree(root).write(effects, encoding='utf-8', xml_declaration=True)
    text = (resources / 'profiles/XDJ_RX3_Mixxx.profile.cfg').read_text()
    mapping = profile / 'controllers/Hercules_DJControl_Inpulse_500_RX3.midi.xml'
    text += f'\n[ControllerPreset]\nDJControl_Inpulse_500 {mapping}\n\n[Controller]\nDJControl_Inpulse_500 1\n'
    with tempfile.NamedTemporaryFile('w', dir=profile, delete=False) as file:
        file.write(text)
        temporary = Path(file.name)
    temporary.chmod(0o600)
    temporary.replace(config)


def desktop_entry(prefix: Path, executable: Path | None = None, icon: Path | None = None) -> str:
    # Desktop Entry escaping differs from shell quoting; escape literal % field codes.
    executable = str(executable or prefix / 'bin/nauticmixxx').replace('%', '%%')
    for character in ('\\', '"', '`', '$'):
        executable = executable.replace(character, '\\' + character)
    executable = executable.replace('\\', '\\\\')
    icon = str(icon or prefix / 'share/icons/hicolor/1024x1024/apps/nauticmixxx.png')
    icon = icon.replace('\\', '\\\\').replace('\n', '\\n')
    return ('[Desktop Entry]\nType=Application\nName=NauticMixxx\n'
            'Comment=RX3-style DJ performance and Rekordbox USB browsing\n'
            f'Exec="{executable}"\nIcon={icon}\nTerminal=false\n'
            'Categories=AudioVideo;Audio;Mixer;\nStartupWMClass=NauticMixxx\n')


def main() -> None:
    prefix = Path(sys.argv[1]).resolve()
    args = sys.argv[2:]
    if args == ['--install-desktop']:
        data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share')))
        entry = data / 'applications/org.nauticsoftware.NauticMixxx.desktop'
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(desktop_entry(prefix))
        print(f'Installed desktop entry: {entry}')
        return
    # Allow a separate test profile using the native flag, without touching the default.
    profile = Path(os.environ.get('NAUTICMIXXX_PROFILE', str(
        Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'NauticMixxx'))).resolve()
    for index, arg in enumerate(args):
        if arg == '--settings-path' and index + 1 < len(args):
            profile = Path(args[index + 1]).expanduser().resolve()
        elif arg.startswith('--settings-path='):
            profile = Path(arg.split('=', 1)[1]).expanduser().resolve()
    # --help and --version must not create personal data.
    if not any(arg in ('--help', '-h', '--version', '-v') for arg in args):
        seed_profile(prefix / 'share/mixxx', profile)
    binary = prefix / 'libexec/nauticmixxx/NauticMixxx'
    os.execv(str(binary), [str(binary), '--resource-path', str(prefix / 'share/mixxx'),
                          '--settings-path', str(profile), *args])


if __name__ == '__main__':
    main()
