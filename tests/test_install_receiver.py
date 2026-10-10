"""Installer boundaries with temporary files; no root/package/network changes."""
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
from install_receiver import camera_numbers, prepare, write_launchers, installation_report
from manage_versions import activate, rollback, versions


def shell(script, **env):
    return subprocess.run(["bash", "-c", 'source "$1"\n' + script, "installer-test", str(ROOT / "install.sh")],
                          env={**os.environ, **env}, capture_output=True, text=True)


class ReceiverInstallerTests(unittest.TestCase):
    def test_full_installer_activation_and_pending_states_with_fake_system(self):
        for mode, expected in (("ready", 0), ("no-p2p", 0), ("mok-pending", 10), ("software-failed", 2)):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = base / "data/kagami"
                (root / "versions/old").mkdir(parents=True)
                (root / "current").symlink_to(root / "versions/old")
                result = shell('''
kagami_platform() { :; }
kagami_install_dependencies() { :; }
kagami_camera_module() { :; }
kagami_secure_boot() { [[ $KAGAMI_TEST_MODE != mok-pending ]] || return 10; }
kagami_install_miraclecast() { :; }
kagami_install_airplay() { :; }
sudo() { printf '%s\\n' "$*" >> "$KAGAMI_TEST_BASE/calls"; }
git() {
    case $* in
        init*) mkdir -p "$3"; cp -a "$KAGAMI_TEST_REPO/apps" "$KAGAMI_TEST_REPO/tools" "$KAGAMI_TEST_REPO/docs" "$KAGAMI_TEST_REPO/README.md" "$KAGAMI_TEST_REPO/LICENSE" "$3/" ;;
        *ls-remote*) printf '%s\\trefs/heads/main\\n' "$KAGAMI_TEST_SHA" ;;
        *rev-parse*) printf '%s\\n' "$KAGAMI_TEST_SHA" ;;
    esac
}
python3() {
    if [[ $1 == */manage_versions.py ]]; then command python3 "$@";
    elif [[ $1 == - && $# == 2 ]]; then command python3 "$@";
    elif [[ $1 == - ]]; then cat > /dev/null; return 0;
    elif [[ $2 == prepare ]]; then
        printf '{"output":"/dev/video10","source":"/dev/video11","interface":"wlan2"}\\n';
    elif [[ $2 == check ]]; then
        case $KAGAMI_TEST_MODE in no-p2p) printf "Smart View unavailable; AirPlay ready\\n" ;; software-failed) return 2 ;; esac;
    elif [[ $2 == launchers ]]; then touch "$KAGAMI_TEST_BASE/launcher";
    else return 99; fi
}
kagami_main
''', KAGAMI_TEST_MODE=mode, KAGAMI_TEST_BASE=str(base), KAGAMI_TEST_REPO=str(ROOT), KAGAMI_TEST_SHA="a" * 40,
                               XDG_DATA_HOME=str(base / "data"), XDG_CONFIG_HOME=str(base / "config"),
                               TMPDIR=str(base))
                self.assertEqual(result.returncode, expected, result.stderr)
                activated = mode != "software-failed"
                self.assertEqual((base / "launcher").exists(), activated)
                self.assertEqual((root / "current").resolve().name.startswith("v2-" + "a" * 40 + "-"), activated)
                self.assertTrue((root / "versions/old").exists())
                calls = (base / "calls").read_text()
                self.assertEqual("restart kagami-receiver-camera.service" in calls, mode != "mok-pending")
                self.assertNotIn("NetworkManager", calls)
                self.assertFalse(list(base.glob("kagami-install.*")))

    def test_missing_p2p_only_disables_smartview_not_airplay_installation(self):
        smart = [{"name": "wifi_direct", "ok": False, "detail": "No P2P driver"},
                 {"name": "network_helper", "ok": False, "detail": "Not installed"}]
        air = [{"name": "airplay_backend", "ok": True, "detail": "UxPlay ready"}]
        common = [{"name": "gtk4", "ok": True, "detail": "GTK4 ready"}]
        report, status = installation_report(smart, air, common)
        self.assertEqual(status, 0)
        self.assertEqual(report["available_transports"], {"smartview": False, "airplay": True})
        self.assertFalse(any(c["required"] for c in report["checks"] if c["transport"] == "smartview"))
        for failed in (air[0], common[0]):
            with self.subTest(check=failed["name"]):
                failed["ok"] = False
                self.assertEqual(installation_report(smart, air, common)[1], 2)
                failed["ok"] = True

    def test_installer_defaults_to_airplay_without_p2p_and_preserves_choice(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            devices, names = base / "dev", base / "sys"
            devices.mkdir(); names.mkdir()
            config = base / "settings.json"
            with patch("install_receiver.p2p_check", return_value={"ok": False}):
                settings = prepare(config, "wlan2", devices=devices, names=names)
                self.assertEqual(settings["preferred_transport"], "airplay")
            launcher, _ = write_launchers(base / "app", config, base / "data", home=base)
            self.assertIn("--preferred-transport airplay", launcher.read_text())
            settings["preferred_transport"] = "usb"
            config.write_text(json.dumps(settings))
            self.assertEqual(prepare(config, devices=devices, names=names)["preferred_transport"], "usb")
            with patch("install_receiver.p2p_check", return_value={"ok": True}):
                self.assertEqual(prepare(config, "wlan3", devices=devices, names=names)["preferred_transport"], "smartview")

    def test_same_commit_skips_download_packages_and_backends(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "data/kagami"
            target = root / ("versions/v2-" + "a" * 40 + "-" + os.uname().machine)
            (target / "tools").mkdir(parents=True)
            (target / "VERSION").write_text("a" * 40 + "\n")
            (target / "tools/run-receiver.sh").touch()
            (root / "current").symlink_to(target)
            result = shell('''
kagami_platform() { :; }
kagami_resolve_ref() { printf '%s\\n' "$KAGAMI_TEST_SHA"; }
kagami_install_dependencies() { return 99; }
kagami_install_miraclecast() { return 99; }
kagami_install_airplay() { return 99; }
git() { return 99; }
sudo() { return 99; }
kagami_main
''', XDG_DATA_HOME=str(Path(temporary) / "data"), XDG_CONFIG_HOME=str(Path(temporary) / "config"),
                           KAGAMI_TEST_SHA="a" * 40)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Already installed", result.stdout)
            self.assertFalse(list(Path(temporary).glob("kagami-install.*")))
            self.assertEqual((root / "current").resolve(), target)

    def test_remote_ref_resolves_annotated_tags_to_commit(self):
        result = shell('''
git() { printf '%s\\trefs/tags/v2.0.0\\n%s\\trefs/tags/v2.0.0^{}\\n' "$KAGAMI_TEST_TAG" "$KAGAMI_TEST_SHA"; }
kagami_resolve_ref v2.0.0
''', KAGAMI_TEST_SHA="a" * 40, KAGAMI_TEST_TAG="b" * 40)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "a" * 40)
        result = shell('git() { return 1; }\nkagami_resolve_ref missing')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot resolve", result.stderr)

    def test_backend_reuse_requires_recipe_platform_and_usable_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            recipe, marker, binary = (base / name for name in ("recipe", "BUILD", "backend"))
            recipe.write_text("pinned recipe")
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            script = 'kagami_backend_is_current "$KAGAMI_TEST_MARKER" "$KAGAMI_TEST_RECIPE" "$KAGAMI_TEST_BINARY"'
            env = dict(KAGAMI_TEST_MARKER=str(marker), KAGAMI_TEST_RECIPE=str(recipe), KAGAMI_TEST_BINARY=str(binary))
            result = shell('kagami_backend_stamp "$KAGAMI_TEST_RECIPE"', **env)
            marker.write_text(result.stdout)
            self.assertEqual(shell(script, **env).returncode, 0)
            recipe.write_text("new pinned recipe")
            self.assertNotEqual(shell(script, **env).returncode, 0)
            marker.write_text(shell('kagami_backend_stamp "$KAGAMI_TEST_RECIPE"', **env).stdout)
            binary.write_text("#!/bin/sh\nexit 1\n")
            self.assertNotEqual(shell(script, **env).returncode, 0)
            binary.write_text("#!/bin/sh\nexit 0\n")
            self.assertNotEqual(shell(script, **env, VERSION_ID="different").returncode, 0)

    def test_application_rollback_preserves_versions_and_rejects_external_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "kagami"
            targets = []
            for sha in ("a" * 40, "b" * 40):
                target = root / ("versions/v2-" + sha + "-x86_64")
                (target / "tools").mkdir(parents=True)
                (target / "VERSION").write_text(sha)
                (target / "tools/run-receiver.sh").touch()
                targets.append(target)
            activate(root, targets[0]); activate(root, targets[1])
            self.assertEqual((root / "previous").resolve(), targets[0])
            self.assertIn("[current]", "\n".join(versions(root)))
            self.assertEqual(rollback(root), targets[0])
            self.assertEqual((root / "previous").resolve(), targets[1])
            self.assertEqual(rollback(root), targets[1])
            self.assertTrue(all(target.exists() for target in targets))
            with self.assertRaises(ValueError):
                activate(root, Path(temporary))
            self.assertEqual((root / "current").resolve(), targets[1])

    def test_piped_dry_run_performs_no_download_or_privileged_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            for name in ("sudo", "git", "apt-get", "meson", "systemctl"):
                path = Path(temporary) / name
                path.write_text("#!/bin/sh\nexit 99\n")
                path.chmod(0o755)
            result = subprocess.run(["bash", "-s", "--", "--dry-run"], input=(ROOT / "install.sh").read_text(),
                                    env={**os.environ, "PATH": temporary + os.pathsep + os.environ["PATH"]},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Ubuntu 24.04 / 26.04", result.stdout)
            self.assertIn("MiracleCast", result.stdout)
            self.assertIn("Secure Boot", result.stdout)

    def test_invalid_ref_is_rejected_before_installation(self):
        result = shell('kagami_platform() { :; }\nkagami_main', KAGAMI_REF="main;touch /tmp/oops")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid KAGAMI_REF", result.stderr)

    def test_current_kernel_module_requires_exact_vermagic_and_successful_build(self):
        for mode in ("match", "mismatch", "build-failure", "missing"):
            with self.subTest(mode=mode):
                result = shell('''
sudo() { [[ $KAGAMI_TEST_MODE != build-failure ]]; }
modinfo() {
    [[ $KAGAMI_TEST_MODE != missing ]] || return 1
    if [[ $KAGAMI_TEST_MODE == mismatch ]]; then printf 'wrong SMP\\n'; else printf '%s SMP\\n' "$2"; fi
}
kagami_camera_module '7.0.0-38-generic'
''', KAGAMI_TEST_MODE=mode)
                self.assertEqual(result.returncode, 0 if mode == "match" else 2, result.stderr)

    def test_secure_boot_disabled_or_enrolled_does_not_request_import(self):
        for mode in ("disabled", "enrolled", "missing-key"):
            result = shell('''
mokutil() { [[ $KAGAMI_TEST_MODE == disabled ]] || printf 'SecureBoot enabled\\n'; }
sudo() {
    if [[ $1 == test ]]; then [[ $KAGAMI_TEST_MODE != missing-key ]];
    elif [[ $2 == --test-key ]]; then return 0;
    else return 99; fi
}
kagami_secure_boot
''', KAGAMI_TEST_MODE=mode)
            self.assertEqual(result.returncode, 2 if mode == "missing-key" else 0, result.stderr)

    def test_reuses_named_nodes_and_avoids_physical_and_symlink_slots(self):
        with tempfile.TemporaryDirectory() as temporary:
            devices, names = Path(temporary) / "dev", Path(temporary) / "sys"
            devices.mkdir(); names.mkdir()
            (devices / "video10").touch()
            (devices / "video11").symlink_to(devices / "absent")
            for number, label in ((10, "Physical Camera"), (20, "Kagami Virtual Camera")):
                path = names / f"video{number}/name"
                path.parent.mkdir()
                path.write_text(label)
                (devices / f"video{number}").touch()
            self.assertEqual(camera_numbers(devices=devices, names=names), [20, 12])
            settings = {"output": "/dev/video10", "source": "/dev/video12"}
            with self.assertRaisesRegex(ValueError, "occupied"):
                camera_numbers(settings, devices=devices, names=names)

    def test_rerun_preserves_settings_and_presets_and_applies_explicit_adapter(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            devices, names = base / "dev", base / "sys"
            devices.mkdir(); names.mkdir()
            path = base / "config/receiver-install.json"
            settings = prepare(path, "wlan2", devices=devices, names=names)
            self.assertEqual((settings["output"], settings["source"]), ("/dev/video10", "/dev/video11"))
            settings.update(width=1920, height=1080, fps=24)
            path.write_text(json.dumps(settings))
            presets = path.parent / "receiver-presets.json"
            presets.write_text('{"my saved crop": 123}')
            self.assertEqual(prepare(path, devices=devices, names=names), settings)
            self.assertEqual(prepare(path, "wlan3", devices=devices, names=names)["interface"], "wlan3")
            self.assertEqual(presets.read_text(), '{"my saved crop": 123}')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                prepare(path, "wlan3;bad", devices=devices, names=names)

    def test_receiver_replaces_launcher_and_passes_literal_paths_and_arguments(self):
        with tempfile.TemporaryDirectory(prefix="kagami install ") as temporary:
            base = Path(temporary) / 'user $x "quote" %value'
            root, config, data = base / "app", base / "settings.json", base / "data"
            base.mkdir()
            config.write_text(json.dumps({"output": "/dev/video20", "source": "/dev/video21", "width": 1280,
                                          "height": 720, "fps": 30, "interface": "wlan2"}))
            launcher, desktop = write_launchers(root, config, data, home=base)
            commands = base / "test-bin"
            commands.mkdir()
            (commands / "id").write_text("#!/bin/sh\nprintf '1000\\n'\n")
            (commands / "id").chmod(0o755)
            target = root / "current/tools/run-receiver.sh"
            target.parent.mkdir(parents=True)
            target.write_text("#!/bin/sh\nprintf '%s\\n' \"$KAGAMI_PYTHON\" \"$@\"\n")
            result = subprocess.run([str(launcher), "smartview-doctor", "--interface", "wlan3"],
                                    env={**os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"]},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), ["/usr/bin/python3", "--source", "/dev/video21", "--output",
                             "/dev/video20", "--width", "1280", "--height", "720", "--fps", "30", "--interface", "wlan2",
                             "smartview-doctor", "--interface", "wlan3"])
            self.assertIn("%%value", desktop.read_text())
            self.assertNotIn("sudo", launcher.read_text())


if __name__ == "__main__":
    unittest.main()
