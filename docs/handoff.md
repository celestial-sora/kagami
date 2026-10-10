> **Maintainer update:** primary target is now **Ubuntu + Samsung Smart View**, ahead of USB. See [Smart View setup/status](smartview-ubuntu.md). The MiracleCast receiver prototype is integrated but physical Galaxy/P2P acceptance remains open; USB is a fallback. Earlier Fedora/USB rollout references below are historical context.

# Kagami V2 handoff · 2026-10-10

Direction: receiver-first, local-first, scrcpy USB screen mirroring into a real V4L2 webcam. The user permits rebuilding inside the original repo and requests direct integration without a PR. Read [Architecture v2](architecture-v2.md), [audit](receiver-audit.md), [plan](implementation-plan.md) and [validation](validation.md).

## Current code

`apps/receiver/kagami_receiver` is the Python/GTK4 reference desktop and GStreamer processing implementation. Start it with `bash tools/run-receiver.sh`; use `doctor`, `devices`, `pair`, `connect` and `mirror` for headless operation. The script sets both Python module paths.

The adapter verifies scrcpy 3.0+ and installed help flags. Documented V4L2 screen sink → named Screen Input loopback → source preview plus crop/rotate/mirror/scale/FPS → persistent YUY2 Virtual Camera loopback. Preview queues are bounded; screen content is never saved by default. Device output guards reuse V1's driver/label checks. Settings only save explicit normalized crop/framing per serial/app-label/captured dimensions.

Output defaults: input `/dev/video11`, output `/dev/video10`, 1280×720 at 30 FPS. Framing changes rebuild only the input processing branch; the writer remains alive. Stop/close/SIGTERM releases owned children. Disconnect produces black output, not background capture or implicit network reconnect. Captured orientation is locked; stop/rotate/restart and use the matching-size preset.

V1 remains intact in `apps/host`, `apps/web-client` and `apps/linux`, with [README_V1](../README_V1.md). `install.sh` now installs V2 on Ubuntu in one curl command, including pinned MiracleCast, helpers and camera service. The historical Fedora installer is `install-v1.sh`; see [installation](installation.md). The shared one-device Fedora helper now accepts a strictly allowed optional label; the V2 helper preflights two different named slots. Do not unload a running camera module.

## Validation / next work

Read current [validation](validation.md); synthetic raw frames and GTK tests do not close hardware acceptance. The authoring environment has no Android/Fedora/V4L2 hardware. Next work is the explicit [hardware checklist](receiver-testing.md): Samsung Camera and TikTok separately, OBS plus a second V4L2 consumer, cable disconnect/reconnect, Stop/exit, orientation and 15-minute stability. Then test authorized Wi-Fi separately and record measured latency.

Smart View/Miracast has an integrated experimental sink with no Galaxy acceptance; Google Cast is research-only. Automatic reconnect/orientation handling, direct-camera mode, final Rust media migration are deferred. V2 curl packaging was added at the maintainer’s explicit request; fresh-host DKMS/Secure Boot acceptance remains pending.

All legacy CI jobs remain; the receiver job executes raw-frame tests and a real GTK smoke check under Xvfb. Pushes to `feat/receiver-first-architecture` run checks without a PR. Preserve the GI/WebRTC ownership regression check when touching V1 media.

[Prior V1 handoff](handoff-v1.md) is historical context, not current direction.
