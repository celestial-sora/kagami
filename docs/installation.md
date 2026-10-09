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

## Installed kernel awaiting reboot

After a Fedora update, the running kernel can be older than the installed `kernel-devel` package, and repositories may no longer provide development files for that older kernel. The installer prefers the running kernel when its matching files exist. Otherwise it can build the camera module for the newest **already installed**, same-architecture kernel with a matching development tree.

Installation then completes with **camera setup pending**, prints the exact kernel to boot, and exits with code **10**. Save your work and reboot into that kernel; the enabled camera service creates the device on boot, so you do not need to reinstall. If a boot menu appears, select the printed kernel. Secure Boot enrollment, when required, is reported separately and can be completed during the same reboot.

The installer does not reboot, change your default boot entry, downgrade, or silently update the kernel. If neither the running kernel nor a newer installed kernel has matching development files, it attempts to install the running kernel's exact `kernel-devel` package. If that package is unavailable, install a matching Fedora kernel/development pair, reboot into it, and rerun the installer.

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
