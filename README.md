# Kagami · 鏡

Turn the **screen of your Android phone** into a real Linux virtual camera. Open Samsung Camera, TikTok effects, or any screen app; Kagami mirrors what it displays, crops the useful region, and publishes it to OBS/Discord through V4L2.

**Primary target: Ubuntu + Samsung Smart View. V2 is an experimental source implementation; physical Galaxy/OBS acceptance pending.** No Android Kagami app, account, TLS setup, cloud relay, or browser camera client is needed for the V2 workflow.

## Run V2

Use [Ubuntu installation](docs/installation.md) for the default Smart View workflow. USB/ADB fallback setup remains in [receiver setup](docs/receiver-setup.md).

Install the new receiver with one command on Ubuntu 24.04 or 26.04:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

Open **Kagami** from your application menu. Dependencies, pinned MiracleCast and camera setup are automatic; sudo authentication and any Secure Boot enrollment still require your action. See [installation](docs/installation.md) for pending prerequisites, updates and paths.

For source/developer diagnostics:

```bash
bash tools/run-receiver.sh smartview-doctor --interface wlo1
bash tools/run-receiver.sh
```

1. Choose **Samsung Smart View**, select a P2P-capable Wi-Fi adapter, and run Check Smart View.
2. Confirm that adapter may disconnect, then Start. The fixed network helper may request polkit authentication; the GUI/media stay unprivileged.
3. On the Galaxy open **Smart View → Kagami**, accept the phone prompt, then open Samsung Camera.
4. Drag/apply a crop over the useful preview and select **Kagami Virtual Camera** in OBS (default `/dev/video10`). `/dev/video11` is the intermediate screen input.
5. Stop from Kagami; the broker restores the adapter's previous network management. This lifecycle is not yet hardware-verified.

This machine's `rtw88_8821ce` driver does not advertise P2P-client/P2P-GO, so real Smart View is blocked until compatible hardware/driver is available. Kagami reports that explicitly. USB Mirror and authorized Wi-Fi ADB Mirror remain selectable fallback paths.

The native GTK4 reference desktop and GStreamer pipeline currently use Python/PyGObject. The original Rust GTK/libadwaita shell is preserved as V1. A Rust media migration is deferred until the new hardware path is proven.

For headless use:

```bash
bash tools/run-receiver.sh devices
bash tools/run-receiver.sh mirror --serial YOUR_ADB_SERIAL --crop 0.1,0.15,0.8,0.6 --output /dev/video10 --source /dev/video11
```

Wi-Fi uses **authorized Android Wireless debugging**, with explicit Pair/Connect controls in the desktop. See [setup](docs/receiver-setup.md) for CLI commands and connection diagnostics. Kagami never switches from USB to a network automatically.

## Capabilities and limits

- USB and Wi-Fi scrcpy screen-mirror adapters share crop/rotation/mirror/scaling/FPS processing and a persistent YUY2 camera writer.
- scrcpy **3.0+**, installed help flags and Linux V4L2 support are checked at runtime. Only documented `--v4l2-sink` output is used.
- Smart View/Miracast has an integrated MiracleCast prototype and synthetic H.264/RTP decoder test, with Galaxy/P2P interoperability still unverified. Google Cast remains research-only.
- Crop removes UI outside the rectangle. Overlays inside it remain. Protected surfaces may be black. Third-party effects only survive when the phone app allows screen mirroring.
- In USB/ADB modes capture orientation is locked when connecting because the intermediate V4L2 sink needs stable dimensions. Stop, rotate the phone, and reconnect; saved crops are keyed by captured size. Output rotation is independent.
- FPS, rate adjustments and approximate host timestamp age are visible. Transport drops and glass-to-glass latency remain unknown until measured.
- No screen images or video are saved by default. Only explicitly saved framing settings are written locally.

## Validation

```bash
python3 -m pip install -r apps/host/requirements.txt  # retained V1 test dependencies
python3 -m unittest discover -s tests -v
KAGAMI_TEST_GST=1 G_DEBUG=fatal-criticals python3 -m unittest discover -s tests -p test_receiver.py -v
xvfb-run -a python3 tools/check_receiver_desktop.py
```

CI keeps V1 host/browser/native/media checks and adds real synthetic raw-frame GStreamer and GTK smoke checks. These do not prove a real phone, kernel camera output or OBS. Follow [hardware testing](docs/receiver-testing.md) and [validation evidence](docs/validation.md).

The original browser bridge remains available in [V1 documentation](README_V1.md) with `install-v1.sh`. The default `install.sh` now installs **V2 on Ubuntu**. Smart View hardware acceptance remains open.

Read [Architecture v2](docs/architecture-v2.md), [implementation plan](docs/implementation-plan.md), [migration audit](docs/receiver-audit.md) and [handoff](docs/handoff.md).

MIT for Kagami source; dependencies retain their own licenses.
