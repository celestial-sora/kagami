#!/usr/bin/env python3
"""Bundle Debian/Ubuntu Python + GTK4 + selected GStreamer plugins with relative RPATH.

Build on Ubuntu 24.04 for glibc 2.39 hosts; no driver/root helper is bundled.
Runtime files/licenses come only from the build host's package manager.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]
# glibc and graphics drivers must belong to the host. Do not bundle Mesa/DRI.
HOST_LIBS = re.compile(r'^(ld-linux.*|lib(c|m|pthread|dl|rt|resolv|util)\.so\..*|lib(EGL|GL|GLX|GLdispatch|OpenGL)\.so\..*)$')
# Only the media paths used by Kagami. In particular, no Python plugin loader.
PLUGINS = ('coreelements', 'app', 'videoconvertscale', 'videocrop', 'videofilter',
           'videorate', 'video4linux2', 'udp', 'rtp', 'rtpmanager', 'mpegtsdemux',
           'videoparsersbad', 'libav', 'audioconvert', 'audioresample', 'volume',
           'level', 'pulseaudio', 'playback', 'typefindfunctions', 'audioparsers')


def build(appdir, backend):
    if appdir.exists():
        raise ValueError('Use a new AppDir path.')
    if not backend.is_file():
        raise ValueError('Supply the staged Kagami-patched UxPlay binary.')
    multiarch = sysconfig.get_config_var('MULTIARCH')
    system_lib = Path('/usr/lib') / multiarch
    if not (system_lib / 'gstreamer-1.0').is_dir():
        raise ValueError('Build AppImages on a Debian/Ubuntu host with installed runtime packages.')
    elfs, package_files = [], set()

    def copy(source, target):
        source, target = Path(source), Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target, follow_symlinks=True)
        package_files.add(str(source.resolve()))
        if target.read_bytes()[:4] == b'\x7fELF':
            elfs.append(target)

    def tree(source, target):
        for path in source.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc', '.a', '.o') and not any(part.startswith('config-') for part in path.parts):
                copy(path, target / path.relative_to(source))

    copy(Path(sys.executable).resolve(), appdir / 'usr/bin/python3')
    pyver = f'python{sys.version_info.major}.{sys.version_info.minor}'
    tree(Path(sysconfig.get_path('stdlib')), appdir / 'usr/lib' / pyver)
    for module in ('gi', 'cairo'):
        tree(Path('/usr/lib/python3/dist-packages') / module, appdir / 'usr/lib/python3/dist-packages' / module)
    tree(system_lib / 'girepository-1.0', appdir / 'usr/lib/girepository-1.0')
    # GI loads these via typelib dlopen rather than ELF NEEDED entries.
    for pattern in ('libgtk-4.so.1', 'libgdk_pixbuf-2.0.so.0', 'libpango-1.0.so.0',
                    'libpangocairo-1.0.so.0', 'libcairo-gobject.so.2', 'libgraphene-1.0.so.0',
                    'libgstreamer-1.0.so.0', 'libgstapp-1.0.so.0', 'libgstvideo-1.0.so.0',
                    'libgstaudio-1.0.so.0', 'libgstbase-1.0.so.0'):
        copy(system_lib / pattern, appdir / 'usr/lib' / pattern)
    for name in PLUGINS:
        copy(system_lib / f'gstreamer-1.0/libgst{name}.so', appdir / f'usr/lib/gstreamer-1.0/libgst{name}.so')
    scanner = next(Path('/usr/lib').glob('**/gstreamer-1.0/gst-plugin-scanner'))
    copy(scanner, appdir / 'usr/libexec/gst-plugin-scanner')
    copy(backend, appdir / 'usr/bin/kagami-uxplay')
    # GIO TLS modules are loaded by directory enumeration, not ELF NEEDED.
    modules = system_lib / 'gio/modules'
    for module in modules.glob('*.so'):
        copy(module, appdir / 'usr/lib/gio/modules' / module.name)
    if (appdir / 'usr/lib/gio/modules').exists():
        subprocess.run(['gio-querymodules', str(appdir / 'usr/lib/gio/modules')], check=True)
    tree(Path('/usr/share/glib-2.0/schemas'), appdir / 'usr/share/glib-2.0/schemas')
    tree(ROOT / 'apps/receiver/kagami_receiver', appdir / 'usr/share/kagami/apps/receiver/kagami_receiver')
    copy(ROOT / 'packaging/appimage/appimage_bootstrap.py', appdir / 'usr/share/kagami/appimage_bootstrap.py')
    copy(ROOT / 'packaging/appimage/AppRun', appdir / 'AppRun')
    (appdir / 'AppRun').chmod(0o755)
    copy(ROOT / 'packaging/appimage/io.kagami.Host.desktop', appdir / 'io.kagami.Host.desktop')
    copy(ROOT / 'apps/receiver/kagami_receiver/icons/hicolor/256x256/apps/io.kagami.Host.png', appdir / 'io.kagami.Host.png')
    (appdir / '.DirIcon').symlink_to('io.kagami.Host.png')
    copy(ROOT / 'LICENSE', appdir / 'usr/share/doc/kagami/LICENSE')
    # Resolve the complete dependency closure before modifying any RPATH.
    inspected = set()
    for elf in elfs:
        if elf in inspected:
            continue
        inspected.add(elf)
        result = subprocess.run(['ldd', str(elf)], capture_output=True, text=True, check=True)
        if 'not found' in result.stdout:
            raise RuntimeError(result.stdout)
        for name, path in re.findall(r'^\s*(\S+) => (/\S+)', result.stdout, re.M):
            if not HOST_LIBS.match(name) and not (appdir / 'usr/lib' / name).exists():
                copy(path, appdir / 'usr/lib' / name)
    for elf in inspected:
        relative = os.path.relpath(appdir / 'usr/lib', elf.parent)
        subprocess.run(['patchelf', '--force-rpath', '--set-rpath', f'$ORIGIN:$ORIGIN/{relative}', str(elf)], check=True)
    # Keep licenses for every Debian package supplying runtime files.
    packages = set()
    paths = sorted(package_files)
    for offset in range(0, len(paths), 100):
        result = subprocess.run(['dpkg-query', '-S', *paths[offset:offset + 100]], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if ': /' in line:
                packages.add(line.split(': /', 1)[0].split(':', 1)[0])
    for package in sorted(packages):
        doc = Path('/usr/share/doc') / package
        if doc.exists():
            for license in doc.glob('copyright*'):
                copy(license, appdir / 'usr/share/doc' / package / license.name)
    tree(Path('/usr/share/common-licenses'), appdir / 'usr/share/common-licenses')
    digest = hashlib.sha256()
    for path in sorted(appdir.rglob('*')):
        if path.is_file():
            digest.update(str(path.relative_to(appdir)).encode())
            digest.update(path.read_bytes())
    (appdir / 'BUILD-ID').write_text(digest.hexdigest()[:16] + '\n')
    (appdir / 'usr/share/doc/kagami/BUILD.txt').write_text(
        subprocess.check_output(['ldd', '--version'], text=True).splitlines()[0] + '\n' +
        subprocess.check_output(['dpkg-query', '-W', *sorted(packages)], text=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('appdir', type=Path)
    parser.add_argument('uxplay', type=Path)
    args = parser.parse_args()
    build(args.appdir.absolute(), args.uxplay.absolute())
