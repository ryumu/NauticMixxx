#!/usr/bin/env python3
"""Verify platform guards without Pi hardware or package installation."""
import importlib.util
import fnmatch
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pi_dev', ROOT / 'scripts/check-raspberry-pi-dev.py')
pi_dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi_dev)


class PiDevelopmentTests(unittest.TestCase):
    def check_platform(self, **changes):
        arguments = dict(system='Linux', machine='aarch64', bits=64, architecture='arm64',
                         model='Raspberry Pi 5 Model B Rev 1.0',
                         release={'ID': 'debian', 'VERSION_CODENAME': 'bookworm'})
        arguments.update(changes)
        return pi_dev.platform_errors(**arguments)

    def test_supported_pi_os_releases(self):
        for identifier in ('debian', 'raspbian'):
            for codename in ('bookworm', 'trixie'):
                with self.subTest(identifier=identifier, codename=codename):
                    self.assertEqual(self.check_platform(release={
                        'ID': identifier, 'VERSION_CODENAME': codename}), [])

    def test_64_bit_kernel_with_32_bit_userland_is_rejected(self):
        self.assertTrue(self.check_platform(bits=32, architecture='armhf'))

    def test_other_hardware_and_os_are_rejected(self):
        for changes in (dict(machine='x86_64'), dict(system='Darwin'),
                        dict(model='Raspberry Pi 4 Model B Rev 1.5'),
                        dict(model='unknown'), dict(release={}),
                        dict(release={'ID': 'debian', 'VERSION_CODENAME': 'bullseye'})):
            with self.subTest(changes=changes):
                self.assertTrue(self.check_platform(**changes))

    def test_tool_version_boundaries(self):
        for value, minimum, expected in (
                ('cmake version 3.21.0', (3, 21, 0), True),
                ('cmake version 3.20.6', (3, 21, 0), False),
                ('6.2.0', (6, 2, 0), True), ('6.1.3', (6, 2, 0), False),
                ('6.8', (6, 2, 0), True), ('', (6, 2, 0), False)):
            with self.subTest(value=value):
                self.assertEqual(pi_dev.version_at_least(value, minimum), expected)

    def test_invalid_build_type_fails_before_download(self):
        # The native build guards reject unsupported build settings on Linux.
        import os
        import platform
        if platform.system() != 'Linux' or platform.machine() not in ('aarch64', 'x86_64'):
            self.skipTest('Native Linux build script only')
        result = subprocess.run(['sh', str(ROOT / 'scripts/build-mixxx-rx3-linux.sh')],
                                env={**os.environ, 'RX3_BUILD_TYPE': 'invalid'},
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('RX3_BUILD_TYPE must be', result.stderr)

    def test_linux_build_selects_usb_safety_regressions(self):
        script = (ROOT / 'scripts/build-mixxx-rx3-linux.sh').read_text()
        expression = re.search(r"--gtest_filter='([^']+)'", script).group(1)
        positive, separator, negative = expression.partition('-')
        for name in (
                'RekordboxUsbSessionTest.DifferentMountedDeviceIdentityRefusesUsbWrites',
                'RekordboxDeviceTest.SnapshotChangesWhenExportOrMountChanges',
                'RekordboxDiscoveryTest.CustomMountedRootIsDiscoveredWithoutLegacyDirectory',
                'RekordboxLinuxMountTest.IdentityChecksDoNotLeakFileDescriptors',
                'RekordboxLazyWaveformTest.FutureRegression',
                'TrackCapabilityPolicyTest.FutureRegression'):
            with self.subTest(name=name):
                self.assertTrue(any(fnmatch.fnmatchcase(name, pattern) for pattern in positive.split(':')))
                self.assertFalse(separator and any(fnmatch.fnmatchcase(name, pattern)
                                                   for pattern in negative.split(':')))


if __name__ == '__main__':
    unittest.main()
