# Validation record · 2026-10-09

## Verified in the authoring environment

- Ubuntu 24.04 execution environment, Python 3.12, aiohttp 3.14.4, Node 24.
- 15 Python auth/protocol/TLS integration tests passed.
- Browser client and browser-test JavaScript syntax checks passed.
- Read-only doctor exits with an actionable missing-dependency/device report instead of starting a fake camera.
- One-command installer batch: 22 Python tests passed locally, including seven installer/configuration scenarios. They exercise actual local TLS generation and preservation, interface selection, literal launcher paths, a no-change piped dry run and invalid privileged-helper input. They do not run DNF, systemd, firewalld or kernel installation.

## GitHub CI evidence

- [Source checks at `0b5b52e`](https://github.com/celestial-sora/kagami/actions/runs/37935062062): all 15 host tests and 7 Chromium scenarios passed on Ubuntu 24.04.
- Chromium exercised responsive layout, a real VP8 synthetic-camera exchange, camera switching, permission denial, cancellation during pending permission, protocol mismatch and host disconnect. The receiver is a browser-local WebRTC fixture, not GStreamer.
- [Initial source checks at `1e443a4`](https://github.com/celestial-sora/kagami/actions/runs/37934155382): `cargo check --workspace` passed with GTK4/libadwaita development libraries. This checks compilation, not native window operation.
- Browser cases now start from a fresh document; fragment-only navigation had previously preserved tracks from the prior test and produced a false failure.

## Not verified here

- Rust/GTK execution and native visual inspection on Fedora. Local compilation was unavailable, but the GitHub compile check above passed.
- GStreamer decoding, GLib pipeline lifecycle, V4L2 writes and OBS integration: GStreamer/PyGObject and `/dev/video*` are absent.
- Physical browser behavior beyond the explicitly recorded Chromium synthetic-camera checks. Chromium is absent from the authoring environment; browser execution occurs in CI.
- Physical Android browser HTTPS/CA onboarding, actual front/rear switching, Wi-Fi/USB paths, capture behavior and latency.
- Fedora installation, kernel module/Secure Boot setup, native visual inspection and hardware acceleration.
- Fresh-Fedora execution of the complete curl installer, akmods/MOK enrollment, uaccess and firewalld behavior. These remain machine-dependent acceptance checks.

The GitHub workflow provides Python, browser and native-build checks. Workflow configuration alone is not evidence of passing checks; inspect the recorded run results.

The installer batch adds ShellCheck, Desktop Entry validation, a native release build and real GStreamer plugin/ICE API checks to CI. These checks do not prove a moving phone image reaches a V4L2 device or OBS.

**Phase 0 hardware acceptance remains open.** Focus, Android screen capture and final packaging were deliberately not advanced before that gate.
