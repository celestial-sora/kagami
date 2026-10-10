> **Maintainer update:** primary target is now **Ubuntu + Samsung Smart View**, ahead of USB. See [Smart View setup/status](smartview-ubuntu.md). The MiracleCast receiver prototype is integrated but physical Galaxy/P2P acceptance remains open; USB is a fallback. Earlier Fedora/USB rollout references below are historical context.

# V2 receiver setup on Fedora

This is a source/developer setup, not a hardware-accepted release. The app runs as your desktop user. Only dependency/module/udev setup needs administrative privileges. Keep Secure Boot enabled and complete signing/enrollment according to the existing [Fedora module guide](fedora-setup.md).

## Dependencies

Install distribution Python/PyGObject, GTK4, Cairo, GStreamer base/good plugins, ADB and scrcpy. For DNF-based Fedora, check package availability for your release:

```bash
sudo dnf install python3 python3-gobject python3-cairo python3-gstreamer1 gtk4 \
  gstreamer1 gstreamer1-plugins-base gstreamer1-plugins-good android-tools scrcpy v4l-utils
```

If your enabled repositories do not provide `scrcpy`, use the [official Linux installation instructions](https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md). Do not assume an arbitrary binary supports V4L2: Kagami checks the installed version and help flags. Require scrcpy 3.0+, GStreamer 1.22+ and GTK4 4.8+. This path uses software-decoded raw frames and does not promise hardware acceleration.

Install/build `v4l2loopback` for the running kernel using the distribution’s signed module/DKMS packaging. The default `install.sh` automates the Ubuntu receiver setup. Do not unload a loaded loopback module to make room for V2.

## Two named camera nodes

`/dev/video10` is the consumer output; `/dev/video11` is scrcpy's intermediate screen input. Use other free slots if needed. The helper rejects occupied non-Kagami devices and never unloads cameras:

```bash
sudo bash packaging/fedora/kagami-receiver-camera-setup 10 11
sudo install -m 644 packaging/fedora/70-kagami-camera.rules /etc/udev/rules.d/70-kagami-camera.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=video4linux
sudo udevadm settle
v4l2-ctl --list-devices
```

These devices are named **Kagami Virtual Camera** and **Kagami Screen Input**, with `exclusive_caps=1`. The session's uaccess ACL grants your active desktop user access. If doctor reports permission denied, inspect the session/ACL and udev rules; never run the GUI as root or chmod physical cameras.

For boot persistence, install both adjacent helpers and a service after your kernel-module preparation service:

```bash
sudo install -D -m 755 packaging/fedora/kagami-camera-setup /usr/local/libexec/kagami-camera-setup
sudo install -D -m 755 packaging/fedora/kagami-receiver-camera-setup /usr/local/libexec/kagami-receiver-camera-setup
```

Use this unit as `/etc/systemd/system/kagami-receiver-camera.service`, replacing numbers as needed:

```ini
[Unit]
Description=Kagami receiver camera nodes
Wants=akmods.service
After=akmods.service systemd-udevd.service systemd-modules-load.service
[Service]
Type=oneshot
ExecStart=/usr/local/libexec/kagami-receiver-camera-setup 10 11
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
```

Then `sudo systemctl daemon-reload` and `sudo systemctl enable --now kagami-receiver-camera.service`. If the legacy camera service also uses video10, both reuse the same named device; never run two app writers simultaneously. Sign/build the module for each installed kernel before changing kernels.

## USB connection

1. Enable Android Developer options and USB debugging.
2. Connect a data-capable USB cable. Unlock the phone and accept its authorization prompt. Kagami never grants permissions for you.
3. Run `bash tools/run-receiver.sh devices`. Unauthorized means authorization is pending; offline means ADB/cable needs attention. Choose a device marked USB/device, not a Wi-Fi/mDNS identity.
4. Open Samsung Camera, then start `bash tools/run-receiver.sh`. Set Input/Output nodes if different from the defaults.
5. Framing order: crop → clockwise quarter-turn → horizontal mirror → aspect-preserving scale → fit letterbox or fill center crop → output FPS/format. The transformed preview shows this framing; the screen preview is the source used for dragging the crop.

scrcpy uses its documented [V4L2 sink](https://github.com/Genymobile/scrcpy/blob/master/doc/v4l2.md) and [locked capture orientation](https://github.com/Genymobile/scrcpy/blob/master/doc/video.md#orientation). Stop and reconnect after changing phone orientation. This mirrors the screen, not direct camera capture; camera-app effects are preserved only if rendered into a capturable surface.

## Wi-Fi connection

Use Android Wireless debugging on a trusted, reachable private network. Pair and connect only when you explicitly choose those actions. Kagami does not enable unauthenticated `adb tcpip` or change networks/firewall rules.

In Android choose **Pair device with pairing code**. Use its pairing IP:port and six-digit code in Kagami. Then enter the main Wireless debugging **IP address & port**, which can differ, and Connect. Choose Wi-Fi Mirror and refresh devices.

CLI alternative:

```bash
bash tools/run-receiver.sh pair --endpoint 192.168.1.20:37123
bash tools/run-receiver.sh connect --endpoint 192.168.1.20:39851
bash tools/run-receiver.sh devices
bash tools/run-receiver.sh mirror --mode wifi --serial 192.168.1.20:39851
```

Addresses and ports above are examples. The pairing code is prompted privately, sent through stdin and never saved in Kagami settings/argv. ADB maintains its standard authorization keys. Reconnect is an explicit action. If Android's port changes, connect to the new displayed port and refresh.

## Diagnostics

`bash tools/run-receiver.sh doctor` checks ADB, scrcpy capabilities, GStreamer plugins and loopback identity/access independently. It returns 2 for missing prerequisites and always reports consumer acceptance as manual/pending.

No frame within 15 seconds: check ADB authorization, scrcpy V4L2 support, the intermediate node, camera-app protected surfaces and logged scrcpy errors. A stopped connection shows black on the persistent output until Stop/reconnect; it does not leave an uncontrolled screen capture running. Unknown transport drops and end-to-end latency are not displayed as measured values.
