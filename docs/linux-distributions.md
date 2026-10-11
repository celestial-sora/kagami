# Linux distribution support and AppImage

Ubuntu remains the primary desktop. The current development installer also selects packages for Debian, Arch and Fedora families. Contributor: celestail-sora.

| Target | Package manager | Minimum/runtime requirements |
| --- | --- | --- |
| Ubuntu 24.04 / 26.04 and newer | apt | Matching `linux-headers-$(uname -r)` |
| Debian 12 / 13 and newer | apt | Matching kernel headers |
| Ubuntu/Debian derivatives (Mint, Pop!_OS, etc.) | apt, detected through `ID_LIKE` | Python 3.10+, GTK 4.8+, GStreamer 1.22+; matching kernel headers |
| Arch and Arch derivatives (EndeavourOS, Manjaro, etc.) | pacman | Full system upgrade; headers selected from the installed kernel package owner |
| Fedora and Fedora derivatives | dnf | Supported mutable workstation release; matching `kernel-devel-$(uname -r)` |

Red Hat/RHEL, Rocky, AlmaLinux, CentOS and other RPM families such as openSUSE are outside this change's scope. `ID` takes precedence over `ID_LIKE`. A package-manager name alone is not evidence that a distribution is supported. All native paths require a systemd desktop, NetworkManager for Smart View, Avahi and a user-session PulseAudio/PipeWire output. Immutable/Atomic/OSTree and non-systemd installations require manual prerequisites; the mutable-host installer refuses them.

Until a new stable release is published, the existing latest stable installer retains its earlier Ubuntu scope. To try the new **development** installer:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

Use `--dry-run` to inspect the plan without changes. Existing settings, crop presets, installed app versions and rollback remain preserved. `--repair` repeats host prerequisites after kernel changes. Source/backends build as the desktop user; only fixed helpers, dependencies and camera setup require authentication. The installer never starts a phone session or disconnects networking. Missing P2P disables Smart View without blocking AirPlay.

## Kernel and repository requirements

Debian/Ubuntu and Arch use their packaged `v4l2loopback-dkms` and tooling. On Fedora, an existing DKMS registration is preserved; otherwise the installer stages upstream v4l2loopback **0.15.4**, commit `0f9ee86760b7f2bea174b7e3e7a1d38845da0ab4`, and builds its userspace utility without root. DKMS builds the module against the running kernel; the installer checks exact `vermagic` before camera setup. Two distinct Kagami-labelled loopbacks and the existing driver/label guard remain mandatory. No physical camera is written to or unloaded.

Arch performs `pacman -Syu` before dependency installation to avoid unsupported partial upgrades. The running kernel must still have an installed package and matching headers after that upgrade. If it was replaced, the installer returns **10**, reports kernel setup pending, and asks you to reboot and rerun; it does not pretend the application installation completed. Custom/AUR-only kernel headers must already be provided by the user; no AUR helper or root AUR build is invoked.

Fedora uses signed configured DNF repositories. Missing packages fail visibly. The installer does not silently add RPM Fusion, disable signature checking, change firewall rules or disable SELinux. For video, Kagami prefers `avdec_h264` and falls back to `openh264dec`. Fedora installs `openh264` and `gstreamer1-plugin-openh264` from its configured signed repositories; Fedora Cisco OpenH264 must be available. If neither H.264 decoder or the `avdec_aac`/`avdec_alac` audio decoders are available, install the appropriate codec-enabled packages for your release/repositories and rerun. The software preflight checks actual plugin availability, rather than accepting package installation as decoder evidence. With a firewall, allow AirPlay/mDNS on the trusted LAN yourself; see [AirPlay](airplay-ubuntu.md). RPM kernel development packages must match the running kernel exactly; reboot into an installed supported kernel if the old development package is no longer available.

Secure Boot uses the distribution's DKMS signing certificate/MOK flow. Missing signing setup is an actionable failure; enrollment/reboot remains pending with exit 10. Secure Boot is never disabled. Fedora's security policy may require administrator-specific setup; no permissive SELinux policy is installed.

Package sources: [Debian v4l2loopback](https://packages.debian.org/search?keywords=v4l2loopback), [Arch kernel/header guidance](https://wiki.archlinux.org/title/V4l2loopback), [Fedora GStreamer libav package](https://packages.fedoraproject.org/pkgs/gstreamer1-plugin-libav/gstreamer1-plugin-libav/), [Fedora OpenH264 guidance](https://fedoraproject.org/wiki/OpenH264).

## AppImage

The initial artifact is **x86_64**. CI builds on Ubuntu 24.04 with a **glibc 2.39** baseline for Ubuntu 24.04+, Debian 13+, current Arch and current Fedora. Debian 12 (glibc 2.36) should use the native installer; this AppImage is not promised there. Building on a newer host raises the binary compatibility floor. AppImage does not imply support for every Linux distribution.

The AppImage bundles Python, PyGObject/Cairo, GTK4, GStreamer, the required media plugins, licensed DejaVu fallback fonts/fontconfig and Kagami's patched pinned UxPlay. Every bundled ELF uses a relative RPATH; no library-search environment is leaked into host `pkexec`, systemctl or the fixed privileged broker. It preserves the approved RGBA artwork, packages library licenses, uses the normal XDG settings/cache directories, and never automatically starts reception or records media.

**Host prerequisites remain required:** the matching V4L2 kernel driver, two named camera nodes/ACLs, Avahi on the same LAN and desktop audio. Smart View additionally requires the installed fixed root-owned helper, MiracleCast and an adapter advertising P2P client/GO. USB/ADB Wi-Fi still require host adb and scrcpy 3+. These privileged/hardware prerequisites cannot live inside an AppImage. Run the native installer once on a supported host; then the AppImage can run independently of the installed app payload.

Download the `kagami-appimage-x86_64` artifact from successful [Checks CI](https://github.com/celestial-sora/kagami/actions/workflows/ci.yml), verify its SHA256SUMS, then:

```bash
sha256sum --check SHA256SUMS
chmod +x Kagami-*-x86_64.AppImage
./Kagami-2.1.0-x86_64.AppImage
```

The guarded release workflow attaches the exact AppImage from successful main CI to future stable releases, together with its checksum. It does not rebuild an untested binary during publication.

If FUSE is unavailable, use the runtime's extraction mode:

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./Kagami-2.1.0-x86_64.AppImage
```

A read-only runtime check (no camera/phone/network session):

```bash
APPIMAGE_EXTRACT_AND_RUN=1 ./Kagami-2.1.0-x86_64.AppImage --appimage-check
```

### Build as a normal user

Use an Ubuntu 24.04 builder with the runtime dependencies from the installer plus `patchelf`, `squashfs-tools`, `fonts-dejavu-core`, and build prerequisites for UxPlay. No root operations occur in this command:

```bash
bash tools/build-appimage.sh "$PWD/.local/appimage-build"
```

Supply a new absolute directory. The script downloads versioned **appimagetool 1.9.1** and **type2-runtime 20251108**, verifies pinned SHA256 digests, builds pinned/patched UxPlay, assembles an AppDir with runtime/licenses, checks its GTK/media/backend imports, then emits the AppImage/checksum. [AppImage packaging](https://docs.appimage.org/packaging-guide/from-source/native-binaries.html).

## Validation boundaries

Distribution CI installs the actual dependency manifests and checks runtime bindings/plugins plus unprivileged pinned backend builds in disposable Debian 12/13, Arch and Fedora containers. AppImage CI tests its packaged runtime after extraction/relocation and GTK under Xvfb. Containers cannot verify host DKMS loading, Secure Boot, camera ACLs, P2P, firewall/SELinux behavior, physical Apple/Galaxy media or OBS. Those host/device acceptance checks remain open outside the previously recorded Ubuntu iPad evidence.

Feature [Checks CI 38118020462](https://github.com/celestial-sora/kagami/actions/runs/38118020462) passes all 11 jobs at `e9fb4c4`, including real Fedora OpenH264 decoding and the same AppImage's complete receiver GTK smoke on Debian 13, Arch and Fedora 44 without host GTK/GStreamer packages. These results validate userspace/runtime portability and staged source compilation, with the hardware boundaries above still open.
