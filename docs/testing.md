# Validation and Phase 0 acceptance

## Automated checks

Run `python3 -m unittest discover -s tests -v`, `node --check apps/web-client/app.js`, `npm run test:browser` after installing Playwright/Chromium, and `cargo check --workspace` with GTK4/libadwaita development packages.

Host tests use real local TLS and HTTP/WebSocket transports. The media backend is a recording test double. Browser tests use a Chromium synthetic camera and real browser peer connections through a local signaling fixture. Neither proves the actual GStreamer/V4L2 path or Android behavior.

## Required hardware gate

- [ ] Record Fedora/kernel, Wayland compositor, OBS, GStreamer and Android/browser versions.
- [ ] Run `doctor`, verify the loopback device/permissions, and confirm moving test bars inside OBS's V4L2 source.
- [ ] Establish trusted phone HTTPS and actual camera permissions without certificate bypasses.
- [ ] Feed live phone camera through the supplied receiver into the same OBS V4L2 source.
- [ ] Stream for 15 minutes at fixed 720p/30; record incoming/output FPS, CPU/RAM, visible stalls and negotiated caps.
- [ ] Repeat front/rear requests, stop/start, tab close, phone lock and network loss/reconnect while OBS keeps the same source.
- [ ] Confirm the no-signal slate appears on disconnect/stall and that the kernel device remains selectable while the host is open.
- [ ] Repeat on USB tethering with external network access unavailable; record the actual local route.
- [ ] Repeat a 1080p/30 host configuration and record any device/codec constraints.
- [ ] Measure glass-to-glass latency with a visible stopwatch/timecode or high-speed camera, reporting method and samples. Do not infer it from HTTPS response time or ICE round-trip time.

Do not advance Phase 0 to complete until live phone frames reach OBS through a real V4L2 device. Record failures as failures; no substitute Browser Source or fake device can satisfy this gate.
