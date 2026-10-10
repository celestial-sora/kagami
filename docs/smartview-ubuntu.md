# Ubuntu + Samsung Smart View (current primary target)

The maintainer changed the primary target from Fedora/USB to **Ubuntu + Samsung Smart View** during implementation. The supplied architecture remains preserved verbatim; this decision changes the rollout priority. Smart View uses Miracast/Wi-Fi Direct, with no ADB/Android Kagami app. USB and ADB Wi-Fi remain fallback paths.

**Status: experimental integrated receiver prototype, not Galaxy-verified.** Synthetic RTP/MPEG-TS/H.264 decoding, framing and GTK checks pass. Actual P2P discovery, negotiation and Samsung Camera surfaces must still be tested with a Galaxy.

## Current machine blocker

On this Ubuntu 26.04 authoring machine, `wlo1` uses `rtw88_8821ce`. `iw phy phy0 info` advertises managed/AP/monitor but **no P2P-client/P2P-GO modes**. Other mentions of P2P under TX/RX capabilities do not prove P2P interface support. Kagami rejects this adapter rather than claiming Smart View is ready. A P2P-capable adapter/driver is necessary. MiracleCast and decoder plugins are also not installed system-wide here.

Check the selected adapter without changing your network:

```bash
bash tools/run-receiver.sh smartview-doctor --interface wlo1
iw dev wlo1 info
iw phy phy0 info
```

Use the actual interface/PHY names. No network services are stopped by diagnostics.

## Ubuntu dependencies and camera nodes

For a compatible Ubuntu host:

```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo python3-cairo python3-gst-1.0 \
  gir1.2-gtk-4.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-libav iw network-manager wpasupplicant \
  policykit-1 v4l-utils v4l2loopback-dkms linux-headers-generic
```

GTK4 4.8+ and GStreamer 1.22+ are required. Install headers matching the actual running kernel when it is not Ubuntu's generic kernel. Secure Boot may require the standard DKMS signing/MOK enrollment step; keep it enabled and complete enrollment manually.

The camera helpers under `packaging/fedora/` contain distribution-independent loopback provisioning; the existing Fedora **installer** is separate. Create two free named slots:

```bash
sudo bash packaging/fedora/kagami-receiver-camera-setup 10 11
sudo install -m 644 packaging/fedora/70-kagami-camera.rules /etc/udev/rules.d/70-kagami-camera.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=video4linux
sudo udevadm settle
```

Do not unload cameras. The helper checks both names before creating anything. Output is `/dev/video10` (**Kagami Virtual Camera**); intermediate input is `/dev/video11` (**Kagami Screen Input**). Run the app as your desktop user.

## MiracleCast and the network broker

Kagami integrates the documented [MiracleCast sink](https://github.com/albfan/miraclecast) and [external-player interface](https://github.com/albfan/miraclecast/wiki/miracle-sinkctl). Source inspected at `0b7f1f1f6586dc65ff480f3cda5c2170a70aa020`. Newer wrappers were inspected, but none provides proof of Samsung interoperability on this machine. No third-party code is vendored into Kagami.

Install MiracleCast from a trusted distribution package if available, or build the inspected source using its [upstream build instructions](https://github.com/albfan/miraclecast/wiki/Building). An Ubuntu source build needs C/Meson/Ninja, pkg-config, readline, GLib, udev and systemd development packages. Use `-Denable-systemd=true -Dbuild-tests=false` when configuring Meson; inspect the installed D-Bus policy location. Ensure `miracle-wifid` and `miracle-sinkctl` are on the system PATH, including their D-Bus policy. Do not replace systemd or stop NetworkManager globally to follow old upstream examples.

Install Kagami's fixed, root-owned network helpers:

```bash
sudo install -D -m 755 packaging/ubuntu/kagami-smartview-helper /usr/local/libexec/kagami-smartview-helper
sudo install -D -m 755 packaging/ubuntu/kagami-smartview-session /usr/local/libexec/kagami-smartview-session
```

At Start, polkit may ask for administrator authentication for the **network helper only**. It validates the chosen adapter/options, temporarily hands that adapter to MiracleCast, advertises the name Kagami, negotiates 1280×720@30 without UIBC/audio, and restores the previous management state at Stop/app exit. The app, decoder and camera writer run unprivileged. No permanent sudoers changes are required. Other adapters and NetworkManager itself are left running.

A single selected radio may lose its router connection while receiving. Prefer a separate compatible adapter if you need the current Wi-Fi connection to remain active. Select **Allow this adapter to disconnect while receiving** only when that is acceptable. The helper never selects a different adapter automatically. Network/P2P lifecycle and restoration remain hardware-unverified; inspect logs if cleanup reports a failure.

## Receive from the Galaxy

1. Run `bash tools/run-receiver.sh`; **Samsung Smart View** is the default mode.
2. Enter the P2P adapter name and press **Check Smart View**. Resolve failed prerequisites first.
3. Confirm the selected adapter may disconnect, then Start. Authenticate the network helper if prompted.
4. On the Galaxy open Quick Settings → **Smart View**, choose **Kagami**, and accept the phone's connection/capture prompt.
5. Open Samsung Camera. Drag a crop over the preview, apply rotation/mirror/fit/fill, then choose **Kagami Virtual Camera** in OBS.
6. Stop in Kagami before restarting. Disconnect also on the phone before a new session. No implicit network reconnection is attempted.

Headless equivalent:

```bash
bash tools/run-receiver.sh smartview --interface YOUR_P2P_ADAPTER --allow-network-disconnect
```

The Miracast stream is decoded once from RTP/MPEG-TS/H.264 into the intermediate camera; the same raw-frame processing and persistent output are used as USB. No screen content is stored. Smart View peer identity is not yet verified, so automatic per-phone presets are deferred for this transport. Protected surfaces and overlays inside the selected crop remain subject to Android/app behavior.

The receiver listens for MiracleCast's negotiated media on UDP 7236. If the host firewall blocks it, inspect and scope a rule to the actual Wi-Fi Direct link/peer; Kagami does not open the port to arbitrary networks. Google Cast is a separate protocol and remains research-only.

## Acceptance gate

On **Ubuntu/Wayland + a P2P-capable adapter + a Galaxy**, prove that Smart View discovers Kagami and receives moving Samsung Camera video. Then prove crop/output in OBS and a second V4L2 consumer, Stop/app-exit restoration, disconnect/reconnect, protected surfaces, and 15-minute stability with empirical latency measurements. Use [the receiver checklist](receiver-testing.md). Until that passes, call this experimental, not a working Smart View release.
