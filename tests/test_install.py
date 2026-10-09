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


class InstallerTests(unittest.TestCase):
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
