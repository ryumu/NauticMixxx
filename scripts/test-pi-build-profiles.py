#!/usr/bin/env python3
"""Exercise Pi wrappers, early guards, compiler profiles and package metadata."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'patches/0064-pi-cpu-profiles-and-retained-overview.patch'


def added_file(name):
    lines = PATCH.read_text().splitlines(keepends=True)
    start = lines.index('+++ b/' + name + '\n') + 1
    result = []
    for line in lines[start:]:
        if line.startswith('diff --git '):
            break
        if line.startswith('+'):
            result.append(line[1:])
    return ''.join(result)


class PiBuildProfiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nautic pi profiles ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / 'checkout with spaces'
        scripts = self.project / 'scripts'
        scripts.mkdir(parents=True)
        for name in ('linux', 'pi4', 'pi5'):
            shutil.copy2(ROOT / f'scripts/build-mixxx-rx3-{name}.sh', scripts)
        (self.project / 'VERSION').write_text('test-version\n')
        (self.project / 'patches').mkdir()
        (self.project / 'patches/0001-fixture.patch').write_text('fixture\n')
        self.log = self.base / 'calls.jsonl'
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        self.executable('uname', '#!/bin/sh\ncase "$1" in -s) echo Linux;; -m) echo "$TEST_MACHINE";; esac\n')
        self.executable('getconf', '#!/bin/sh\necho 64\n')
        sha = shutil.which('sha256sum')
        self.executable('sha256sum', '#!/bin/sh\nif [ "${1:-}" = -c ]; then cat >/dev/null; exit 0; fi\n'
                        f'exec "{sha}" "$@"\n')
        logger = ('#!/usr/bin/python3\nimport json, os, sys\n'
                  'with open(os.environ["CALL_LOG"], "a") as log:\n'
                  '    log.write(json.dumps(sys.argv) + "\\n")\n')
        self.executable('cmake', logger)
        self.executable('python3', logger)
        for name in ('curl', 'tar', 'git'):
            self.executable(name, '#!/bin/sh\necho unexpected external work >&2\nexit 99\n')

    def executable(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def build(self, wrapper, **changes):
        env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
               'CALL_LOG': str(self.log), 'TEST_MACHINE': 'aarch64',
               'RX3_BUILD_TESTING': 'OFF', 'RX3_BUILD_JOBS': '1'}
        for name in ('RX3_BUILD_ROOT', 'RX3_BUILD_TYPE', 'RX3_PI_PROFILE', 'RX3_PI_LTO'):
            env.pop(name, None)
        env.update(changes)
        return subprocess.run(['sh', str(self.project / f'scripts/build-mixxx-rx3-{wrapper}.sh')],
                              env=env, capture_output=True, text=True)

    def prepare_work(self, suffix):
        work = self.project / f'build/test-candidate/test-version-linux-aarch64{suffix}'
        source = work / 'mixxx-2.5.6'
        (source / 'src/test').mkdir(parents=True)
        (source / 'src/test/trackcapabilitypolicy_test.cpp').touch()
        (source / '.rx3-patched').write_text(hashlib.sha256(b'fixture\n').hexdigest() + '\n')
        (work / 'mixxx-2.5.6.tar.gz').touch()
        return work

    def test_wrappers_select_fixed_profiles_and_separate_roots(self):
        for wrapper, suffix, profile in (('linux', '', 'off'), ('pi4', '-pi4', 'pi4'),
                                         ('pi5', '-pi5', 'pi5')):
            with self.subTest(wrapper=wrapper):
                work = self.prepare_work(suffix)
                self.log.unlink(missing_ok=True)
                extra = {'RX3_PI_PROFILE': 'pi5' if wrapper == 'pi4' else 'pi4'} if wrapper != 'linux' else {}
                result = self.build(wrapper, **extra)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = [json.loads(line) for line in self.log.read_text().splitlines()]
                configure = next(call for call in calls if '-S' in call)
                self.assertIn(str(work / 'native'), configure)
                self.assertIn('-DNAUTIC_PI_PROFILE=' + profile, configure)
                self.assertIn('-DNAUTIC_PI_LTO=OFF', configure)
                self.assertIn('-DOPTIMIZE=portable', configure)
                self.assertIn('-DCMAKE_PROJECT_INCLUDE=' + str(self.project / 'packaging/linux/desktop-build.cmake'), configure)
                self.assertTrue(any('--register-build' in call for call in calls))

    def test_invalid_options_and_wrong_architecture_stop_before_download(self):
        for wrapper, changes in (
                ('linux', {'RX3_PI_PROFILE': 'invalid'}),
                ('linux', {'RX3_PI_LTO': 'ON'}),
                ('pi4', {'RX3_PI_LTO': 'invalid'}),
                ('pi4', {'TEST_MACHINE': 'x86_64'}),
                ('pi5', {'TEST_MACHINE': 'x86_64'})):
            with self.subTest(wrapper=wrapper, changes=changes):
                self.assertNotEqual(self.build(wrapper, **changes).returncode, 0)
                self.assertFalse(self.log.exists())
                self.assertFalse((self.project / 'build').exists())

    def test_existing_other_cpu_profile_is_rejected(self):
        work = self.prepare_work('-pi5')
        (work / 'native').mkdir()
        (work / 'native/CMakeCache.txt').write_text('NAUTIC_PI_PROFILE:STRING=pi4\n')
        result = self.build('pi5')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('different CPU profile', result.stderr)
        self.assertFalse(self.log.exists())

    def test_lto_is_explicit_and_custom_root_is_preserved(self):
        work = self.prepare_work('-pi4')
        result = self.build('pi4', RX3_BUILD_ROOT=str(work), RX3_PI_LTO='ON')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        configure = next(call for call in calls if '-S' in call)
        self.assertIn('-DNAUTIC_PI_LTO=ON', configure)
        self.assertIn(str(work / 'native'), configure)


class PiCompilerProfiles(unittest.TestCase):
    def test_cmake_profiles_compile_and_validate_targets(self):
        with tempfile.TemporaryDirectory(prefix='nautic pi cmake ') as directory:
            source = Path(directory) / 'source'
            source.mkdir()
            (source / 'NauticPi.cmake').write_text(added_file('cmake/NauticPi.cmake'))
            (source / 'main.cpp').write_text('int main() { return 0; }\n')
            (source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.22)\n'
                'project(PiProfiles LANGUAGES C CXX)\nset(OPTIMIZE portable CACHE STRING "")\n'
                'include(NauticPi.cmake)\nadd_executable(profile main.cpp)\n')
            arm = platform.system() == 'Linux' and platform.machine() == 'aarch64'
            for profile, lto in (('off', 'OFF'), ('pi4', 'OFF'), ('pi5', 'OFF'), ('pi5', 'ON')):
                with self.subTest(profile=profile, lto=lto):
                    build = Path(directory) / f'{profile}-{lto}'
                    result = subprocess.run(['cmake', '-S', str(source), '-B', str(build), '-G', 'Ninja',
                        '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON', '-DNAUTIC_PI_PROFILE=' + profile,
                        '-DNAUTIC_PI_LTO=' + lto], capture_output=True, text=True)
                    if profile != 'off' and not arm:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('64-bit ARM Linux', result.stdout + result.stderr)
                        continue
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    subprocess.run(['cmake', '--build', str(build)], check=True, capture_output=True)
                    subprocess.run([str(build / 'profile')], check=True)
                    command = json.loads((build / 'compile_commands.json').read_text())[0]['command']
                    if profile == 'off':
                        self.assertNotIn('-mcpu=', command)
                        self.assertNotIn('-DNAUTIC_PI_PROFILE=', command)
                    else:
                        self.assertIn('-mcpu=cortex-a' + ('72' if profile == 'pi4' else '76'), command)
                        self.assertIn('-DNAUTIC_PI_PROFILE=' + profile[-1], command)
                        self.assertEqual('-flto' in command, lto == 'ON')
            for profile, optimize, lto, error in (
                    ('invalid', 'portable', 'OFF', 'must be off, pi4 or pi5'),
                    ('off', 'portable', 'ON', 'requires a Pi profile'),
                    ('pi4', 'native', 'OFF', 'OPTIMIZE=portable' if arm else '64-bit ARM Linux')):
                build = Path(directory) / f'rejected-{profile}'
                result = subprocess.run(['cmake', '-S', str(source), '-B', str(build),
                    '-DNAUTIC_PI_PROFILE=' + profile, '-DOPTIMIZE=' + optimize,
                    '-DNAUTIC_PI_LTO=' + lto], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stdout + result.stderr)

    def test_metadata_reads_actual_cmake_cache(self):
        spec = importlib.util.spec_from_file_location('stage', ROOT / 'packaging/linux/stage-package.py')
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'mixxx-2.5.6'
            self.assertEqual(stage.optimization_settings(source)['pi_profile'], 'off')
            native = source.parent / 'native'
            native.mkdir()
            (native / 'CMakeCache.txt').write_text('OPTIMIZE:STRING=portable\nNAUTIC_PI_PROFILE:STRING=pi5\n'
                'NAUTIC_PI_CPU:INTERNAL=cortex-a76\nNAUTIC_PI_LTO:BOOL=ON\n')
            self.assertEqual(stage.optimization_settings(source), dict(optimization='portable',
                pi_profile='pi5', cpu='cortex-a76', lto=True))


if __name__ == '__main__':
    unittest.main()
