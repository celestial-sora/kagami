# Kagami · 鏡

A local phone camera bridge for Linux. Your phone sends video; your computer exposes **Kagami Virtual Camera** as a real V4L2 device for OBS.

**Current state: Phase 0 source prototype, hardware acceptance pending.** The HTTPS/pairing service has automated tests. The GStreamer receiver and native Rust shell require the checks below on a Linux machine. This is not a completed v0.1 release.

## Install on Fedora

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

Run as your desktop user. The installer handles dependencies, virtual-camera setup, native build, configuration, TLS and an application-menu launcher. See [installation](docs/installation.md) for Secure Boot enrollment, updates and exact scope. Android certificate trust and camera permission remain first-time phone actions.

## Manual developer setup

Follow [Fedora setup](docs/fedora-setup.md) for system packages and the one-time virtual camera setup. Then:

1. Copy `config.example.json` to `config.json`. Set `host` to the computer's reachable Wi-Fi or USB IPv4 address. TLS paths are relative to this file.
2. Create host certificates for that address:

   ```bash
   python3 tools/create_tls.py --host 192.168.1.50
   ```

3. Transfer **only** `.local/tls/ca.pem` to your phone through a trusted local channel. Follow [pairing and TLS](docs/pairing-and-tls.md); the browser must trust the certificate before it can use the camera.
4. Check the host:

   ```bash
   PYTHONPATH=apps/host python3 -m kagami_host doctor --config config.json
   ```

5. Start the reference host or native shell:

   ```bash
   PYTHONPATH=apps/host python3 -m kagami_host --config config.json
   ```

   ```bash
   cargo run -p kagami-linux
   ```

6. Open the pairing URL or scan the native window's QR code on your phone, then press **Start camera**.
7. In OBS, add **Video Capture Device (V4L2)** and select **Kagami Virtual Camera**.

The `192.168.1.50` address above is an example. Use your computer's actual address. `127.0.0.1` is only for local developer checks and cannot pair a separate phone.

## What is implemented

- HTTPS host with one-time pairing, an expiring secure session, Origin validation and one active sender.
- Offline phone client: camera permission, preview, front/rear request, 720p/1080p capture presets, preview mirroring and teardown/reconnect.
- GStreamer reference receive path: WebRTC VP8 → decoded I420 → fixed-size YUY2 → `v4l2sink`.
- Persistent output pipeline with a no-signal slate and bounded queues between phone sessions.
- Read-only environment diagnostics and a guarded V4L2 test-pattern command.
- Rust GTK4/libadwaita native shell for helper start/stop, QR pairing and frame diagnostics.

## Important scope

Phase 0 uses Python/PyGObject to expose the media spike while the native shell is Rust. This is an explicit integration seam, **not the final Rust media architecture**. Once the [hardware acceptance](docs/testing.md) passes, migrate the validated pipeline into `gstreamer-rs` and complete native preview/interface selection.

The current video codec is **VP8 only** for a small reproducible baseline. H.264/hardware acceleration, Kagami Focus, Android MediaProjection, audio, iOS, RPM/AppImage packaging and automatic certificate renewal remain later milestones. Android sources have not been fabricated before the Phase 0 gate passes.

CI passes 22 Python host/installer tests, seven Chromium synthetic-camera scenarios, a native release build, and real GStreamer plugin/ICE API and teardown checks. Actual Fedora installation and the Android → GStreamer → V4L2 → OBS streaming path remain unverified. Consult [validation status](docs/validation.md) for exact evidence and limitations.

## Developer checks

```bash
python3 -m pip install -r apps/host/requirements.txt
python3 -m unittest discover -s tests -v
node --check apps/web-client/app.js
npm install
npx playwright install chromium
npm run test:browser
cargo check --workspace
```

Browser tests use a synthetic Chromium camera and a browser-local signaling fixture. Host tests use real TLS/HTTP/WebSocket transports with a recording media test double. Neither suite substitutes for V4L2/OBS hardware testing.

Read [architecture](docs/architecture.md), [USB networking](docs/usb-tethering.md), [security](docs/security.md), [troubleshooting](docs/troubleshooting.md), and the supplied [implementation plan](docs/implementation-plan.md).

## License

MIT for Kagami source. System dependencies, including GStreamer, GTK and v4l2loopback, retain their own licenses.
