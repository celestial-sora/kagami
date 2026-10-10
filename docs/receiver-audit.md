> **Maintainer update:** primary target is now **Ubuntu + Samsung Smart View**, ahead of USB. See [Smart View setup/status](smartview-ubuntu.md). The MiracleCast receiver prototype is integrated but physical Galaxy/P2P acceptance remains open; USB is a fallback. Earlier Fedora/USB rollout references below are historical context.

# Receiver-first migration audit · 2026-10-10

## Baseline inspected

Fresh clone of `celestial-sora/kagami`, main at `c8f0ff3`. Read AGENTS, handoff, implementation plan, validation, host/media/V4L2 code, Rust shell, installer and Actions workflow before changes. No pre-existing worktree changes were overwritten.

V1 consists of Python/aiohttp local HTTPS/authenticated WebRTC (VP8), a browser camera client, a Python/GStreamer receiver with persistent V4L2 output, and a Rust GTK/libadwaita pairing shell. V1 has no scrcpy/ADB adapter, native live preview, crop pipeline or proven Samsung Camera/TikTok screen path. Existing V4L2 identity guards, bounded queues, slate/writer lifecycle and Fedora module preparation are useful and preserved.

The latest executable baseline Actions run was successful: [Checks at 93399aa](https://github.com/celestial-sora/kagami/actions/runs/37951587540). The later c8f0ff3 evidence-only commit did not trigger CI due to path filters. No current baseline CI defect was found. Local Python initially lacked aiohttp; installing test-only dependencies resolved that environment issue without changing application requirements.

## Migration implemented

- `apps/receiver/kagami_receiver`: separate V2 entry point, GTK4 reference desktop, ADB discovery/authorized wireless pairing, capability-checked scrcpy screen adapter, transport-independent framing and persistent raw-frame camera output.
- Documented `scrcpy --v4l2-sink` feeds a named intermediate loopback; GStreamer performs crop/rotation/mirror/scale/fit/fill/FPS and exposes a different output node. No dependency on private scrcpy server wire formats, browser-camera replacement, or an Android Kagami app.
- Reference desktop uses existing Python/GI expertise. Rust V1 remains available; moving V2 into Rust is deferred until hardware proof, avoiding simultaneous protocol and language migrations.
- Explicit USB/Wi-Fi selection and manual reconnect; lock the captured orientation to avoid V4L2 resolution changes. Crop settings are normalized and keyed by device/app-label/captured size. The app label is user supplied, not read from personal Android app data.
- Keep one camera writer alive with black output after disconnect; bounded queues/latest preview storage; stop/exit reaps the owned scrcpy process group. Device identity guards reject physical cameras, and locks prevent multiple Kagami receivers owning the same nodes.
- Two-device Fedora provisioning builds on the existing one-device helper; V1 callers remain compatible. No module unload, silent network changes, root GUI or automatic Android permission grants.
- Preserve V1 code, tests, archived install-v1.sh and README_V1.md. Existing handoff/plan are archived as `*-v1.md`; the new plan follows the supplied Architecture v2, preserved verbatim in `architecture-v2.md`.
- Add headless contract tests, opt-in real GStreamer synthetic-frame tests, GTK/Xvfb smoke check and a receiver CI job. Keep all legacy CI jobs. Feature-branch pushes run CI without requiring a PR.

## Remaining acceptance

This environment is Ubuntu 26.04, Python 3.14 with system GTK4/GStreamer 1.28.2, plus a Python 3.12 test runtime. There is no physical Android phone, Fedora host or `/dev/video*`. Samsung preview, TikTok effects, actual loopback writes, OBS/Discord, USB/Wi-Fi stability, Fedora setup, kernel switching and measured glass-to-glass latency remain unverified.

Smart View/Miracast has an integrated experimental MiracleCast sink; Galaxy interoperability is unverified. Google Cast is research-only. Direct camera capture, automatic physical-orientation changes, hardware acceleration, automatic reconnect are deferred. The maintainer explicitly requested V2 curl installation: install.sh now targets the Ubuntu native receiver; physical installation acceptance is pending. Do not advertise these as supported.
