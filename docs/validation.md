# Validation record · 2026-10-09

## Verified in the authoring environment

- Ubuntu 24.04 execution environment, Python 3.12, aiohttp 3.14.4, Node 24.
- 15 Python auth/protocol/TLS integration tests passed.
- Browser client and browser-test JavaScript syntax checks passed.
- Read-only doctor exits with an actionable missing-dependency/device report instead of starting a fake camera.

## Not verified here

- Rust/GTK native compilation: Rust, Cargo and native development libraries are unavailable; toolchain/package installation could not complete in this environment.
- GStreamer decoding, GLib pipeline lifecycle, V4L2 writes and OBS integration: GStreamer/PyGObject and `/dev/video*` are absent.
- Playwright browser scenarios: Playwright is present, but the Chromium executable is absent. Test source is included; no browser test is counted as passed.
- Physical Android browser HTTPS/CA onboarding, actual front/rear switching, Wi-Fi/USB paths, capture behavior and latency.
- Fedora installation, kernel module/Secure Boot setup, native visual inspection and hardware acceleration.

The GitHub workflow provides Python, browser and native-build checks once published. Its results must be inspected separately; workflow configuration alone is not evidence of passing checks.

**Phase 0 hardware acceptance remains open.** Focus, Android screen capture and final packaging were deliberately not advanced before that gate.
