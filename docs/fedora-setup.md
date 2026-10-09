# Fedora developer setup

These are reproducible setup instructions for the target machine, not a claim that this execution environment is Fedora or has tested the driver.

## Userspace packages

```bash
sudo dnf install python3-gobject python3-aiohttp gstreamer1 \
  gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-bad-free \
  libnice-gstreamer1 openssl
```

Native shell build dependencies:

```bash
sudo dnf install rust cargo pkgconf-pkg-config gtk4-devel libadwaita-devel
```

Use the system Python so it can import the distribution's PyGObject. A separately bundled Python or a virtual environment without system packages may not see `gi`. The native shell accepts `KAGAMI_PYTHON` and an absolute `KAGAMI_ROOT` when these need to be specified explicitly.

## Virtual camera driver

Install a distribution-appropriate `v4l2loopback` module for the running kernel. Check your enabled repositories and Secure Boot signing requirements; Kagami does not install repositories, rebuild kernels, or disable Secure Boot automatically. See [upstream setup](https://github.com/v4l2loopback/v4l2loopback#installation).

After the module is installed, pick an unused device number. For example, after checking that `/dev/video10` is free:

```bash
sudo modprobe v4l2loopback video_nr=10 card_label="Kagami Virtual Camera" exclusive_caps=1
v4l2-ctl --device /dev/video10 --all
```

`v4l2-ctl` is supplied by the distribution's `v4l-utils` package. Normal host operation needs read/write access to this device through the distribution's device ACL/group policy; keep Kagami unprivileged. Do not broadly chmod all cameras or unload a module while another app is using it.

The writer checks `VIDIOC_QUERYCAP`: driver must be `v4l2 loopback` and card name must include `Kagami`. This prevents choosing a physical camera by mistake.

## First OBS proof

```bash
bash tools/test-pattern.sh /dev/video10
```

In OBS add **Video Capture Device (V4L2)** and choose **Kagami Virtual Camera**, 1280 × 720, 30 FPS. Confirm moving test bars. Stop the test-pattern process before starting the receiver; two writers must not own the same device.

With `exclusive_caps=1`, camera consumers may discover the device only after a producer opens it. Start the pattern/host first, then refresh the OBS device list. This is not OBS's own virtual camera button.

## Network and firewall

Set `config.json` to the actual reachable IPv4 address of the chosen interface. The server binds that address only. Allow HTTPS TCP on the configured port plus the local WebRTC UDP traffic on that interface/subnet. Do not open an Internet-facing forwarding rule. The spike does not yet configure a restricted ICE UDP port range; keep firewall changes scoped to the trusted local link and record the policy used in the acceptance report.

Package references: [libnice-gstreamer1](https://packages.fedoraproject.org/pkgs/libnice/libnice-gstreamer1/), [GStreamer bad-free plugins](https://packages.fedoraproject.org/pkgs/gstreamer1-plugins-bad-free/gstreamer1-plugins-bad-free/).
