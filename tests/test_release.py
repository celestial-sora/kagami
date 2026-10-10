"""Release artifacts contain committed sources and a pinned installer."""
import hashlib
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def fixture(self, base):
        repo = base / 'repo'
        (repo / 'tools').mkdir(parents=True)
        (repo / 'docs/releases').mkdir(parents=True)
        (repo / 'tools/build-release.sh').write_bytes((ROOT / 'tools/build-release.sh').read_bytes())
        (repo / 'install.sh').write_bytes((ROOT / 'install.sh').read_bytes())
        (repo / 'VERSION').write_text('2.0.0\n')
        (repo / 'docs/releases/v2.0.0.md').write_text('Release notes\n')
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Release Test',
                        '-c', 'user.email=release@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        return repo

    def test_archive_checksums_and_default_tag(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = self.fixture(base)
            (repo / 'untracked-private.txt').write_text('must not ship')
            output = base / 'release'
            result = subprocess.run(['bash', str(repo / 'tools/build-release.sh'), str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            sha = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
            self.assertEqual((output / 'COMMIT').read_text().strip(), sha)
            for line in (output / 'SHA256SUMS').read_text().splitlines():
                digest, filename = line.split('  ', 1)
                self.assertEqual(hashlib.sha256((output / filename).read_bytes()).hexdigest(), digest)
            with tarfile.open(output / 'kagami-v2.0.0-source.tar.gz') as archive:
                self.assertNotIn('kagami-v2.0.0/untracked-private.txt', archive.getnames())
                self.assertEqual(archive.extractfile('kagami-v2.0.0/install.sh').read(), (repo / 'install.sh').read_bytes())
            installer = output / 'install-kagami.sh'
            plan = subprocess.run(['bash', str(installer), '--dry-run'], capture_output=True, text=True)
            self.assertEqual(plan.returncode, 0, plan.stderr)
            self.assertIn('default: v2.0.0.', plan.stdout)
            # Exercise the actual chosen default without installing or resolving a network ref.
            result = subprocess.run(['bash', '-c', '''source "$1"
kagami_platform() { :; }
kagami_resolve_ref() { printf '%s' "$1" > "$KAGAMI_TEST_REF"; return 98; }
kagami_main
''', 'release-test', str(installer)], env={'PATH': '/usr/bin:/bin', 'HOME': str(base),
                                         'KAGAMI_TEST_REF': str(base / 'selected-ref')},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 98)
            self.assertEqual((base / 'selected-ref').read_text(), 'v2.0.0')

    def test_dirty_sources_are_not_packaged(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            repo = self.fixture(base)
            (repo / 'install.sh').write_text('changed source')
            output = base / 'release'
            result = subprocess.run(['bash', str(repo / 'tools/build-release.sh'), str(output)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())
