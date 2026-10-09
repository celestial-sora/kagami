"""Installer safety/config tests. No package or kernel installation is performed."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from install_config import choose_link, prepare
from install_launchers import desktop_quote, write_launchers


def interface(name, host, prefix=24):
    return {"ifname": name, "addr_info": [{"family": "inet", "scope": "global", "local": host, "prefixlen": prefix}]}


def select_kernel(running, installed, ready):
    # Simulate RPM inventory/readiness without touching packages or /boot.
    env = {**os.environ, "KAGAMI_TEST_INSTALLED": "\n".join(installed),
           "KAGAMI_TEST_READY": ":".join(ready)}
    return subprocess.run(["bash", "-c", '''
source "$1"
rpm() { printf '%s\\n' "$KAGAMI_TEST_INSTALLED"; }
uname() { printf 'x86_64\\n'; }
kagami_kernel_ready() { [[ :$KAGAMI_TEST_READY: == *":$1:"* ]]; }
kagami_select_kernel "$2"
''', "kernel-test", str(ROOT / "install.sh"), running],
                          env=env, capture_output=True, text=True)


def installer_shell(script, **variables):
    return subprocess.run(["bash", "-c", 'source "$1"\n' + script,
                           "installer-test", str(ROOT / "install.sh")],
                          env={**os.environ, **variables}, capture_output=True, text=True)


class InstallerTests(unittest.TestCase):
    def test_installed_kernel_inventory_includes_older_versions_and_filters_arch(self):
        result = installer_shell('''
uname() { printf 'x86_64\\n'; }
rpm() { printf '%s\\n' '7.2.9-200.fc44.x86_64' '7.2.7-200.fc44.x86_64' '7.2.9-200.fc44.x86_64' '7.2.10-200.fc44.aarch64'; }
kagami_installed_kernels
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["7.2.7-200.fc44.x86_64", "7.2.9-200.fc44.x86_64"])

    def test_archive_url_uses_installed_kernel_version_and_signing_key(self):
        for version, release, key in (("7.2.8", "200.fc44", "dbfcf71c6d9f90a6"),
                                      ("6.19.10", "300.fc44", "01234567ABCDEF12")):
            kernel = f"{version}-{release}.x86_64"
            result = installer_shell('''
uname() { printf 'x86_64\\n'; }
rpm() { printf 'RSA/SHA256, date, Key ID %s' "$KAGAMI_TEST_KEY"; }
kagami_kernel_devel_url "$KAGAMI_TEST_KERNEL"
''', KAGAMI_TEST_KERNEL=kernel, KAGAMI_TEST_KEY=key)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(),
                             f"https://kojipkgs.fedoraproject.org/packages/kernel/{version}/{release}/"
                             f"data/signed/{key[-8:].lower()}/x86_64/kernel-devel-{kernel}.rpm")

    def test_archive_url_rejects_unsigned_foreign_and_unsafe_kernels(self):
        for kernel, key in (("../../kernel", "dbfcf71c6d9f90a6"),
                            ("7.2.8-200.el10.x86_64", "dbfcf71c6d9f90a6"),
                            ("7.2.8-200.fc44.aarch64", "dbfcf71c6d9f90a6"),
                            ("7.2.8-200.fc44.x86_64", "(none)")):
            result = installer_shell('''
uname() { printf 'x86_64\\n'; }
rpm() { printf 'Key ID %s' "$KAGAMI_TEST_KEY"; }
kagami_kernel_devel_url "$KAGAMI_TEST_KERNEL"
''', KAGAMI_TEST_KERNEL=kernel, KAGAMI_TEST_KEY=key)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_devel_install_preserves_versions_and_requires_signed_archive_rpm(self):
        for mode in ("ready", "repository", "archive", "unavailable"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix="kagami kernel ") as directory:
                calls, marker = Path(directory) / "calls", Path(directory) / "ready"
                calls.touch()
                if mode == "ready":
                    marker.touch()
                result = installer_shell('''
uname() { printf 'x86_64\\n'; }
rpm() { printf 'Key ID dbfcf71c6d9f90a6'; }
kagami_kernel_ready() { [[ -f $KAGAMI_TEST_MARKER ]]; }
sudo() {
    printf '%s\\n' "$*" >> "$KAGAMI_TEST_CALLS"
    if [[ $KAGAMI_TEST_MODE == repository || ( $KAGAMI_TEST_MODE == archive && $* == *https://* ) ]]; then
        touch "$KAGAMI_TEST_MARKER"; return 0
    fi
    return 1
}
kagami_ensure_kernel_devel '7.2.8-200.fc44.x86_64'
''', KAGAMI_TEST_MODE=mode, KAGAMI_TEST_MARKER=str(marker), KAGAMI_TEST_CALLS=str(calls))
                self.assertEqual(result.returncode, 1 if mode == "unavailable" else 0, result.stderr)
                commands = calls.read_text().splitlines()
                self.assertEqual(len(commands), {"ready": 0, "repository": 1, "archive": 2, "unavailable": 2}[mode])
                for command in commands:
                    self.assertIn("--setopt=installonly_limit=0", command)
                if len(commands) == 2:
                    self.assertIn("--setopt=localpkg_gpgcheck=True", commands[1])
                    self.assertIn("/data/signed/6d9f90a6/", commands[1])

    def test_camera_preparation_builds_every_installed_kernel(self):
        self._check_camera_preparation(mismatch=False)

    def test_camera_preparation_rejects_a_module_for_the_wrong_kernel(self):
        self._check_camera_preparation(mismatch=True)

    def _check_camera_preparation(self, mismatch):
        kernels = [f"7.2.{patch}-200.fc44.x86_64" for patch in (7, 8, 9)]
        with tempfile.TemporaryDirectory() as directory:
            calls = Path(directory) / "calls"
            result = installer_shell('''
kagami_installed_kernels() { printf '%s\\n' "$KAGAMI_TEST_KERNELS"; }
kagami_ensure_kernel_devel() { printf 'devel %s\\n' "$1" >> "$KAGAMI_TEST_CALLS"; }
sudo() { printf '%s\\n' "$*" >> "$KAGAMI_TEST_CALLS"; }
modinfo() {
    if [[ $KAGAMI_TEST_MISMATCH == 1 && $2 == 7.2.8-* ]]; then printf 'wrong-kernel SMP\\n';
    else printf '%s SMP\\n' "$2"; fi
}
kagami_prepare_camera_kernels
''', KAGAMI_TEST_KERNELS="\n".join(kernels), KAGAMI_TEST_CALLS=str(calls),
                                     KAGAMI_TEST_MISMATCH="1" if mismatch else "0")
            self.assertEqual(result.returncode, 2 if mismatch else 0, result.stderr)
            expected = []
            for kernel in kernels[:2] if mismatch else kernels:
                expected.extend([f"devel {kernel}", f"akmods --force --kernels {kernel} --akmod v4l2loopback"])
            self.assertEqual(calls.read_text().splitlines(), expected)
            if mismatch:
                self.assertIn("does not match", result.stderr)

    def test_kernel_selection_prefers_running_kernel_with_matching_files(self):
        current, newer = "7.2.8-200.fc44.x86_64", "7.2.9-200.fc44.x86_64"
        result = select_kernel(current, [newer, current], [current, newer])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), current)

    def test_kernel_selection_stages_newest_complete_installed_kernel(self):
        current = "7.2.8-200.fc44.x86_64"
        installed = ["7.2.9-200.fc44.x86_64", current, "7.2.11-200.fc44.x86_64",
                     "7.2.10-200.fc44.x86_64"]
        result = select_kernel(current, installed, [installed[0], installed[3]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), installed[3])

    def test_kernel_selection_rejects_downgrades_other_arches_and_devel_only(self):
        current = "7.2.8-200.fc44.x86_64"
        installed = ["7.2.7-200.fc44.x86_64", "7.2.9-200.fc44.aarch64", current]
        result = select_kernel(current, installed, installed[:2] + ["7.2.10-200.fc44.x86_64"])
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_selects_default_lan_and_ignores_vpn_container_and_public_addresses(self):
        links = [interface("docker0", "172.17.0.1", 16), interface("wg0", "10.1.0.2"),
                 interface("enp1s0", "8.8.8.8"), interface("wlan0", "192.168.5.8"),
                 interface("usb0", "192.168.42.100")]
        self.assertEqual(choose_link(links, [{"dev": "wlan0"}])["subnet"], "192.168.5.0/24")
        self.assertEqual(choose_link(links, [], "192.168.42.100")["interface"], "usb0")
        with self.assertRaises(ValueError):
            choose_link(links, [], "8.8.8.8")
        with self.assertRaises(ValueError):
            choose_link([interface("eth0", "192.168.5.8", 0)], [])

    def test_missing_network_does_not_create_certificates(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                prepare(directory, "/dev/video10", [], [])
            self.assertFalse((Path(directory) / "tls").exists())

    def test_fresh_setup_and_rerun_preserve_settings_and_ca(self):
        with tempfile.TemporaryDirectory() as directory:
            links = [interface("wlan0", "192.168.5.8")]
            result = prepare(directory, "/dev/video10", links, [])
            path = Path(result["config"])
            before_ca = (Path(directory) / "tls/ca.pem").read_bytes()
            values = json.loads(path.read_text())
            values["width"], values["height"], values["fps"] = 1920, 1080, 15
            path.write_text(json.dumps(values))
            before_config = path.read_bytes()
            again = prepare(directory, "/dev/video10", links, [])
            self.assertEqual(again["host"], result["host"])
            self.assertEqual(path.read_bytes(), before_config)
            self.assertEqual((Path(directory) / "tls/ca.pem").read_bytes(), before_ca)
            self.assertEqual(os.stat(Path(directory) / "tls/ca.key").st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                prepare(directory, "/dev/video11", links, [])
            self.assertEqual(path.read_bytes(), before_config)

    def test_existing_config_with_wrong_ip_certificate_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            links = [interface("wlan0", "192.168.5.8")]
            result = prepare(directory, "/dev/video10", links, [])
            path = Path(result["config"])
            values = json.loads(path.read_text())
            values["host"] = "192.168.5.9"
            path.write_text(json.dumps(values))
            with self.assertRaises(subprocess.CalledProcessError):
                prepare(directory, "/dev/video10", [interface("wlan0", "192.168.5.9")], [])

    def test_launch_paths_with_spaces_dollars_quotes_and_percent_are_literal(self):
        with tempfile.TemporaryDirectory(prefix="kagami install ") as directory:
            base = Path(directory) / 'user $x "quote" %value'
            root, config, data = base / "app", base / "settings.json", base / "data"
            launcher, desktop = write_launchers(root, config, data, home=base)
            # Fake id lets this path/argument test run even inside a root container.
            commands = base / "test-bin"
            commands.mkdir(parents=True)
            (commands / "id").write_text("#!/bin/sh\nprintf '1000\\n'\n")
            (commands / "id").chmod(0o755)
            binary = root / "current/bin/kagami-linux"
            binary.parent.mkdir(parents=True)
            binary.write_text("#!/bin/sh\nprintf '%s\\n' \"$KAGAMI_ROOT\" \"$KAGAMI_CONFIG\" \"$1\"\n")
            binary.chmod(0o755)
            env = {**os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"]}
            result = subprocess.run([str(launcher), "a literal $argument"], env=env, check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout.splitlines(), [str(root / "current"), str(config), "a literal $argument"])
            self.assertIn("%%value", desktop.read_text())
            self.assertNotIn("sudo", launcher.read_text())
            with self.assertRaises(ValueError):
                desktop_quote("bad\npath")

    def test_dry_run_from_pipe_does_not_invoke_system_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "sudo"
            fake.write_text("#!/bin/sh\nexit 99\n")
            fake.chmod(0o755)
            env = {**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"]}
            result = subprocess.run(["bash", "-s", "--", "--dry-run"], input=(ROOT / "install.sh").read_text(), env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("RPM Fusion Free", result.stdout)
            self.assertIn("Secure Boot", result.stdout)

    def test_invalid_camera_helper_input_never_calls_modprobe(self):
        for value in ("../../video0", "10;touch", "256"):
            result = subprocess.run(["bash", str(ROOT / "packaging/fedora/kagami-camera-setup"), value], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == "__main__":
    unittest.main()
