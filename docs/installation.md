# One-command Fedora installation

For DNF-based Fedora Workstation, run as your ordinary desktop user:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

The installer requests your sudo password for system setup. It installs GTK/Rust/GStreamer/Python packages, enables **RPM Fusion Free** when needed, installs its `akmod-v4l2loopback` and userspace tools, builds Kagami without root, prepares local HTTPS, and adds **Kagami** to your application menu. The first source build can take several minutes; Internet is needed for installation and updates, while streaming stays local.

It supports DNF-based Fedora, including KDE with GTK libraries. Fedora Atomic/Silverblue, containers, other distributions and machines without administrative access receive an explanation. The installation workflow is source-tested; an actual fresh Fedora installation remains part of the hardware acceptance gate.

## After installation

1. Open **Kagami** from the application menu and press **Start host**.
2. Transfer only the printed `ca.pem` file to Android through a trusted local channel and import the CA. See [trusted HTTPS setup](pairing-and-tls.md). The QR code alone cannot grant certificate trust.
3. Scan Kagami's QR, press **Start camera**, and grant the phone's camera permission.
4. In OBS select **Video Capture Device (V4L2) → Kagami Virtual Camera**.

The host installer cannot grant Android certificate trust or camera permission on your behalf. Those remain first-time phone actions.

## Secure Boot

The installer preserves the existing akmods signing key, or creates one before building the camera module. When Secure Boot is enabled and this key is not enrolled, it requests an enrollment password using `mokutil`. Reboot, choose **Enroll MOK**, and confirm using that password. The camera setup service runs after reboot; no second installation command is required for that enrollment step.

In this case it reports **camera setup pending** and exits with code 10 rather than claiming a ready camera. It never disables Secure Boot or certificate verification. Unsigned previously installed modules, package build errors or denied permissions report an actionable failure. See the distribution's `/usr/share/doc/akmods/README.secureboot` and [RPM Fusion guidance](https://rpmfusion.org/Howto/Secure%20Boot).

## Multiple kernel versions

The virtual camera driver is compiled separately for each installed Fedora `kernel-core` version of the host architecture. The installer obtains that kernel's exact `kernel-devel` package, builds its v4l2loopback module through RPM Fusion akmods, and verifies the module's `vermagic` matches the requested kernel. Kagami's application/configuration can be reused when switching between those kernels.

Fedora repositories often retain only the latest kernel development packages. If an installed older version is unavailable there, the installer tries the **signed Fedora Koji archive**, using the version, release, architecture and signing key of that installed kernel. DNF signature checking is explicitly enabled for this direct RPM URL. If signed development files or a compatible driver cannot be prepared for a kernel, installation reports that exact kernel and fails visibly.

Exact development-package transactions preserve installed versions without changing your global DNF settings. The installer keeps boot defaults and existing kernels, and starts the camera on the running kernel once its module is prepared. A reboot is still needed for pending Secure Boot enrollment, or when the running kernel is outside the installed standard Fedora kernel inventory; those cases print the required action and exit with code **10**.

For subsequent kernel updates, RPM Fusion's existing `95-akmodsposttrans.install` hook invokes `akmods@<kernel>.service`. Its package dependencies provide matching development files, and the enabled `akmods.service` can build at boot before Kagami's camera service starts. No extra Kagami download/build daemon is added. Keep the kernel/development packages together when updating; Internet is needed for package installation, while an already prepared camera stays local at runtime.

Automatic preparation covers standard Fedora `kernel-core` packages. Custom/debug/real-time kernels require their own matching development packages and driver setup. The driver must support the kernel API; a successful source test or build for one version does not prove compatibility with every future kernel.

## Updates and paths

Run the same curl command again to update. The current Git SHA and architecture identify an installed version; an already built version is reused. The installer preserves config, capture settings and the existing CA. It retains previous app versions, and switches the active version after setup succeeds.

|Item|Default path|
|---|---|
|App versions|`~/.local/share/kagami/versions/`|
|Active app|`~/.local/share/kagami/current`|
|Launcher|`~/.local/bin/kagami`|
|Desktop entry|`~/.local/share/applications/io.kagami.Host.desktop`|
|Configuration|`~/.config/kagami/config.json`|
|TLS files|`~/.config/kagami/tls/`|
|Root camera helper|`/usr/local/libexec/kagami-camera-setup`|
|Camera boot service|`/etc/systemd/system/kagami-camera.service`|
|Camera device ACL rule|`/etc/udev/rules.d/70-kagami-camera.rules`|

`XDG_DATA_HOME` and `XDG_CONFIG_HOME` are honored. No GUI or media process runs as root; the boot helper only creates/reuses the named loopback and never unloads another device. The active desktop session receives device access through `uaccess`.

Auto-configuration prefers the default private LAN interface, ignores container/VPN addresses, and includes the currently available LAN/USB IPs in the initial certificate. To choose a specific currently attached address on first install:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | KAGAMI_HOST=192.168.42.100 bash
```

Existing configurations using an unavailable address or a certificate without the matching IP are preserved and rejected. Address migration/certificate renewal is still a prototype limitation; follow [TLS](pairing-and-tls.md) and [USB setup](usb-tethering.md) before changing that configuration.

If firewalld is running, the installer adds rules in the selected interface's zone, restricted to its private subnet **and configured destination IP**: TCP HTTPS (default 8443) and bounded ICE ports (default UDP 50000–50100). It does not reload unrelated runtime firewall rules, alter routing, or enable Internet port forwarding. On a custom firewall, apply the equivalent local rules yourself. USB networking must use its own reachable address and subnet.

Inspect the setup plan without changes:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash -s -- --dry-run
```

`KAGAMI_REF` on the `bash` side selects a branch, tag or Git commit for repeatable installs. See [validation](validation.md) for exactly what was tested and [manual Fedora setup](fedora-setup.md) for the individual commands.

Package sources: [RPM Fusion v4l2loopback packaging](https://github.com/rpmfusion/v4l2loopback-kmod), [Fedora RPM Fusion setup](https://docs.fedoraproject.org/en-US/quick-docs/rpmfusion-setup/), [GStreamer ICE port properties](https://github.com/GStreamer/gstreamer/blob/main/subprojects/gst-plugins-bad/gst-libs/gst/webrtc/ice.c).
