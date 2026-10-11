"""Distribution/package dispatch is tested without changing host packages/cameras."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def shell(code, **env):
    return subprocess.run(['bash', '-eu', '-c', 'source "$1"\n' + code, 'test', str(ROOT / 'install.sh')],
                          env={**os.environ, **env}, capture_output=True, text=True)


class LinuxPackagingTests(unittest.TestCase):
    def test_native_and_derivative_dispatch(self):
        for name, version, like, family in (
            ('ubuntu', '24.04', 'debian', 'debian'), ('ubuntu', '26.04', 'debian', 'debian'),
            ('debian', '12', '', 'debian'), ('debian', '13', '', 'debian'),
            ('linuxmint', '22', 'ubuntu debian', 'debian'), ('pop', '24.04', 'ubuntu', 'debian'),
            ('arch', '', '', 'arch'), ('endeavouros', '', 'arch', 'arch'),
            ('manjaro', '26.0', 'arch', 'arch'), ('fedora', '44', '', 'rpm'),
            ('myremix', '1', 'fedora', 'rpm'),
            ('nobara', '44', 'rhel centos fedora', 'rpm')):
            with self.subTest(name=name):
                result = shell('kagami_distribution\nprintf "%s" "$KAGAMI_FAMILY"',
                               ID=name, VERSION_ID=version, ID_LIKE=like)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, family)

    def test_unsupported_and_old_distributions_fail_before_mutation(self):
        for name, version in (('opensuse', '16'), ('rhel', '9'), ('rocky', '9.6'),
                              ('ubuntu', '22.04'), ('debian', '11'), ('rhel', '10'), ('almalinux', '10')):
            result = shell('kagami_distribution', ID=name, VERSION_ID=version, ID_LIKE='rhel fedora' if name in ('rhel', 'rocky', 'almalinux') else '')
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_package_managers_preserve_signatures_and_arch_upgrade(self):
        for family, manager in (('debian', 'apt-get'), ('arch', 'pacman'), ('rpm', 'dnf')):
            result = shell('sudo() { printf "%s\\n" "$*"; }\nkagami_refresh_packages\nkagami_packages test-package',
                           KAGAMI_FAMILY=family)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(all(line.startswith(manager + ' ') for line in result.stdout.splitlines()))
            if family == 'arch':
                self.assertIn('-Syu', result.stdout)
                self.assertNotIn('-Sy ', result.stdout)
            if family == 'rpm':
                self.assertIn('gpgcheck=1', result.stdout)
                self.assertNotIn('nogpgcheck', result.stdout)

    def test_arch_headers_follow_kernel_owner_and_missing_kernel_is_pending(self):
        for owner in ('linux', 'linux-lts', 'linux-zen', 'linux-hardened', 'linux-manjaro'):
            result = shell('pacman() { printf "%s" "$TEST_OWNER"; }\nkagami_arch_kernel_package test-kernel', TEST_OWNER=owner)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), owner + '-headers')
        result = shell('pacman() { return 1; }\nkagami_arch_kernel_package absent-kernel')
        self.assertEqual(result.returncode, 10, result.stderr)
        result = shell('pacman() { printf "bad;package"; }\nkagami_arch_kernel_package test-kernel')
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_rpm_repository_failure_is_not_ignored(self):
        result = shell('sudo() { return 1; }\nkagami_packages missing-package', KAGAMI_FAMILY='rpm')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Fedora', result.stderr)

    def test_dependency_manifests_include_bindings_media_and_safe_camera_tools(self):
        for family, required in (
            ('debian', ('python3-gi-cairo', 'gir1.2-gtk-4.0', 'gstreamer1.0-libav', 'v4l2loopback-dkms')),
            ('arch', ('python-gobject', 'gtk4', 'gst-libav', 'v4l2loopback-dkms')),
            ('rpm', ('python3-gobject', 'gtk4', 'gstreamer1-plugin-libav', 'dkms'))):
            result = shell('kagami_dependency_packages', KAGAMI_FAMILY=family)
            self.assertEqual(result.returncode, 0, result.stderr)
            for package in required:
                self.assertIn(package, result.stdout.splitlines())
            self.assertFalse(any('$running' in line or '$headers' in line for line in result.stdout.splitlines()))
