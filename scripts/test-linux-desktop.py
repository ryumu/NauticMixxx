#!/usr/bin/env python3
"""Exercise the real CMake hook, stable desktop launcher and mapping upgrades."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, env=None, check=True):
    result = subprocess.run([str(arg) for arg in args], env=env, text=True, capture_output=True)
    if check and result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result


with tempfile.TemporaryDirectory(prefix='nautic desktop ') as directory:
    base = Path(directory)
    project = base / 'checkout with spaces'
    shutil.copytree(ROOT / 'packaging/linux', project / 'packaging/linux',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('LICENSE.md', 'THIRD_PARTY_NOTICES.md', 'VERSION', 'docs/LINUX-RASPBERRY-PI.md',
                 'branding/iCon-macOS-Dark-1024x1024@1x.png', 'profile/XDJ_RX3_Mixxx.profile.cfg'):
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, path)
    for name in ('Hercules_DJControl_Inpulse_500_RX3', 'Pioneer_DDJ_FLX4_RX3',
                 'Pioneer_DDJ_FLX6_RX3', 'Pioneer_Roland_RX3'):
        (project / 'controllers' / name).mkdir(parents=True)
    script = project / 'controllers/Pioneer_DDJ_FLX4_RX3/Pioneer-DDJ-FLX4-script.js'
    script.write_text('first mapping\n')
    (project / 'skins/XDJ_RX3_Mixxx').mkdir(parents=True)
    (project / 'skins/XDJ_RX3_Mixxx/skin.xml').write_text('<skin/>')
    (project / 'effects/chains').mkdir(parents=True)
    home = base / 'home'
    home.mkdir()
    env = {**os.environ, 'HOME': str(home), 'XDG_DATA_HOME': str(home / 'data'),
           'XDG_CONFIG_HOME': str(home / 'config')}
    env.pop('NAUTICMIXXX_PROFILE', None)
    desktop = project / 'packaging/linux/desktop.py'
    state = project / 'build/desktop' / f'latest-{os.uname().machine}.json'

    def make_build(name, banner, installed=True):
        work = project / 'build' / name
        source = work / 'mixxx-2.5.6'
        source.mkdir(parents=True)
        (source / 'LICENSE').write_text('upstream fixture license')
        (source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.22)\n'
                                            'project(DesktopHook LANGUAGES C)\nadd_executable(mixxx main.c)\n')
        (source / 'main.c').write_text('#include <stdio.h>\nint main(void) { puts("' + banner + '"); return 0; }\n')
        if installed:
            (work / 'stage/share/mixxx/controllers').mkdir(parents=True)
        run('cmake', '-S', source, '-B', work / 'native', '-G', 'Ninja',
            '-DCMAKE_PROJECT_INCLUDE=' + str(project / 'packaging/linux/desktop-build.cmake'), env=env)
        run('cmake', '--build', work / 'native', '--target', 'mixxx', env=env)
        return work

    first = make_build('version-one', 'one', installed=False)
    assert not state.exists(), 'an uninstalled first build must not replace the desktop app'
    (first / 'stage/share/mixxx/controllers').mkdir(parents=True)
    run('python3', desktop, '--publish-build', first, env=env)
    assert run('python3', desktop, '--version', env=env).stdout.strip() == 'one'

    # Install once, then leave both entries untouched across build/version changes.
    (home / 'config').mkdir()
    (home / 'config/user-dirs.dirs').write_text('XDG_DESKTOP_DIR="$HOME/Desk with spaces"\n')
    run('python3', desktop, '--install-desktop', env=env)
    entry = home / 'Desk with spaces/NauticMixxx.desktop'
    saved_entry = entry.read_bytes()
    assert str(desktop) in entry.read_text() and str(first) not in entry.read_text()
    assert (home / 'data/applications/org.nauticsoftware.NauticMixxx.desktop').read_bytes() == saved_entry
    assert not (home / 'config/NauticMixxx').exists(), '--version must not create a profile'

    (project / 'VERSION').write_text('2.1.0\n')
    second = make_build('new-version-other-root', 'two')
    assert json.loads(state.read_text())['prefix'] == str(second / 'stage')
    assert run('python3', desktop, '--version', env=env).stdout.strip() == 'two'
    assert entry.read_bytes() == saved_entry, 'a fixed desktop entry must follow new builds'
    shutil.rmtree(first)
    assert run('python3', desktop, '--version', env=env).stdout.strip() == 'two'
    make_build('not-installed-yet', 'unpublished', installed=False)
    assert json.loads(state.read_text())['prefix'] == str(second / 'stage')

    profile = home / 'config/NauticMixxx'
    (profile / 'controllers').mkdir(parents=True)
    (profile / 'mixxx.cfg').write_bytes(b'user settings')
    (profile / 'mixxxdb.sqlite').write_bytes(b'user library')
    mapping = profile / 'controllers' / script.name
    mapping.write_bytes(b'old mapping')
    script.write_text('updated mapping\n')
    # No C/C++ changes: changing a bundled mapping must also refresh the app.
    run('cmake', '--build', second / 'native', '--target', 'mixxx', env=env)
    run('python3', desktop, env=env)
    assert mapping.read_bytes() == script.read_bytes()
    assert (profile / 'mixxx.cfg').read_bytes() == b'user settings'
    assert (profile / 'mixxxdb.sqlite').read_bytes() == b'user library'
    assert len(list((profile / 'controllers/.nautic-backups').glob('*.bak'))) == 1

    published = second / 'stage/libexec/nauticmixxx/NauticMixxx'
    saved_hash = hashlib.sha256(published.read_bytes()).digest()
    (second / 'mixxx-2.5.6/main.c').write_text('invalid C source\n')
    assert run('cmake', '--build', second / 'native', '--target', 'mixxx', env=env, check=False).returncode
    assert hashlib.sha256(published.read_bytes()).digest() == saved_hash
    assert run('python3', desktop, '--version', env=env).stdout.strip() == 'two'

print('Linux desktop: build hook, new roots, failed builds, mapping-only updates and profile preservation: OK')
