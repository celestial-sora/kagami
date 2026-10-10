# Kagami · 鏡

Mirror a phone's visible screen, crop its camera/app preview, and publish it as **Kagami Virtual Camera** for OBS/Discord on Ubuntu.

The native desktop offers **Samsung Smart View**, **AirPlay**, USB Mirror and authorized ADB Wi-Fi Mirror. AirPlay uses [UxPlay](https://github.com/FDH2/UxPlay) with iPhone/iPad/Mac on the same local network. Smart View uses [MiracleCast](https://github.com/albfan/miraclecast) with a Galaxy and Linux Wi-Fi Direct support. Both wireless receivers are experimental; physical phone/OBS acceptance is pending.

## Install

Run as your ordinary desktop user on Ubuntu 24.04 or 26.04:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

The installer sets up GTK4/GStreamer, pinned MiracleCast/UxPlay, AirPlay discovery, two virtual camera nodes and the **Kagami** application-menu launcher. It requests sudo for system setup; Secure Boot enrollment may need a password and reboot. Run the same command to update. See [installation](docs/installation.md).

## Connect

| Mode | Sender action | Host prerequisite |
|---|---|---|
| Samsung Smart View | Galaxy → Smart View → Kagami | Driver advertising P2P-client/P2P-GO; selected adapter may disconnect |
| AirPlay | iPhone/iPad/Mac → Screen Mirroring → Kagami | Same local network with Avahi discovery; Wi-Fi Direct is unnecessary |
| USB Mirror | Authorize USB debugging | Data cable, ADB and scrcpy 3.0+ |
| Wi-Fi ADB Mirror | Explicit Wireless debugging Pair/Connect | Private network, ADB and scrcpy 3.0+ |

1. Open Kagami, choose a mode and run its Check button. For Smart View confirm that the selected adapter may disconnect.
2. Click **Start**, then select **Kagami** on the sender.
3. Drag/apply a crop over the useful preview and select **Kagami Virtual Camera** in OBS. Default output is `/dev/video10`; `/dev/video11` is internal screen input.
4. Click **Stop** to stop decoding and the owned receiver process. Smart View also restores selected-adapter management.

The former browser connection URL, QR generator, browser camera client and HTTPS pairing service have been removed. Use the sender's device discovery list. Native Samsung Smart View speaks Miracast; AirPlay requires an AirPlay sender and is an additional transport, not a Smart View replacement.

## Capabilities and limits

- Shared crop → clockwise rotation → mirror → scale/fit/fill → FPS processing; bounded previews and a persistent YUY2 output with black fallback on disconnect.
- No cloud, account or default image/video recording. AirPlay audio plays through Ubuntu's selected sound output for speakers and OBS Desktop Audio; the virtual camera carries video only.
- AirPlay receives H264/RTP over a private local bridge and fits the screen into a fixed 1280×720 input canvas. Portrait input has side borders; crop them out. Stop/restart and adjust crop after rotating the phone. Wireless phone identity/preset persistence is not implemented.
- ADB capture orientation is locked at connection. Only authorized ADB devices have per-device/app/captured-size saved presets.
- Crop removes overlays outside the rectangle. Overlays inside remain; protected surfaces may be black. Effects survive only when the sender app permits screen mirroring.
- The authoring RTL8821CE's current `rtw88_8821ce` driver does not advertise P2P client/GO. It previously supported Miracast under Windows; Linux-driver alternatives should be evaluated before concluding hardware replacement is necessary. This does not affect AirPlay's same-LAN path.
- Actual Galaxy/Apple compatibility, network restoration, real kernel-camera writes, OBS/Discord and end-to-end latency remain unverified. See [validation](docs/validation.md) and [hardware testing](docs/receiver-testing.md).

## Developer checks

```bash
python3 -m unittest discover -s tests -v
KAGAMI_TEST_GST=1 G_DEBUG=fatal-criticals python3 -m unittest discover -s tests -v
xvfb-run -a python3 tools/check_receiver_desktop.py
bash tools/run-receiver.sh airplay-doctor
bash tools/run-receiver.sh smartview-doctor --interface wlo1
```

See [AirPlay setup](docs/airplay-ubuntu.md), [Smart View setup](docs/smartview-ubuntu.md), [ADB setup](docs/receiver-setup.md), [architecture](docs/architecture.md) and [handoff](docs/handoff.md). Kagami source is MIT; external MiracleCast and UxPlay retain their own licenses and run as separate processes.

The installer checks the active commit first, skips unchanged downloads/builds, and reuses verified MiracleCast/UxPlay builds on app-only updates. It shows numbered progress and preserves previous app versions: `kagami versions`, `kagami rollback`. Use the same curl command with `bash -s -- --repair` to repeat system setup. Release tags are supported through `KAGAMI_REF`; the stable GitHub Release channel is planned. See [installation details](docs/installation.md).
