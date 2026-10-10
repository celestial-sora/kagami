# Kagami (鏡) — Codex CLI handoff

Prepared: 2026-10-09, Asia/Bangkok.
Repository: https://github.com/celestial-sora/kagami.git
Snapshot: `main` at `57084c03719fb0cf5b445dc7bd10645ccd27534a`, before this documentation commit.
Status: **Phase 0 source prototype; physical-device acceptance is still open.**

## Start here

Read `AGENTS.md`, this file, [the implementation plan](implementation-plan.md), [validation](validation.md), and [installation](installation.md). Fetch current remote state and inspect the worktree before editing. This handoff is a snapshot; newer code and recorded test evidence take precedence.

The next engineering goal is to validate and fix the existing vertical slice on actual Fedora/Wayland with an Android phone and OBS. Preserve the implementation that already exists. Complete Phase 0 before expanding into Focus or Android screen capture. If hardware is unavailable, complete independent code work and report the blocked checks explicitly.

## Product and decisions to preserve

- Linux is the local host/server; the phone sends camera or, later, screen video.
- The output must be a genuine V4L2 camera named **Kagami Virtual Camera**, selectable as an OBS Video Capture Device. A Browser Source, pasted stream URL, or OBS-only virtual-camera workaround does not satisfy the goal.
- Runtime communication stays on LAN or USB tethered IP networking. No mandatory Internet, cloud relay, accounts, analytics, external signaling, STUN/TURN service, or CDN assets.
- Native Linux UI: Rust + GTK4/libadwaita. Android first; other platforms come later.
- Current receiver: Python/PyGObject + GStreamer as an explicit Phase 0 integration seam. Validate it before moving media into Rust; do not rebuild the stack merely to match the proposed future crate layout.
- Current baseline: one video track, VP8, 720p/30 output; 1080p/30 is configurable. H.264/hardware encoding is a later compatibility task. Do not promise 4K/60, transparent screen capture, or audio.
- The user wants a **single curl installation command**, useful intermediate commits, and few integrated pushes to main. Communicate concisely in Thai and address the user as คุณหนู.

## What exists

| Area | Implementation and entry points |
| --- | --- |
| Native host shell | `apps/linux/src/main.rs`: start/stop the Python helper, config path, QR pairing, session/device status and FPS diagnostics. A live native video preview and interface picker remain unfinished. |
| HTTPS host | `apps/host/kagami_host/server.py`, `session.py`, `protocol.py`: local HTTPS, pairing, authenticated WebSocket signaling, expiration and a single active sender. |
| Media | `apps/host/kagami_host/media.py`: WebRTC VP8 → decode → normalized I420 → YUY2 → `v4l2sink`; persistent output writer and a no-signal slate. Bounded queues and generation checks protect reconnects. |
| Device checks | `apps/host/kagami_host/v4l2.py`: V4L2 ioctl identity checks reject physical cameras. `doctor.py` reports missing dependencies, device access and TLS issues. |
| Phone page | `apps/web-client/`: local mobile camera permission/preview, front/rear request, capture presets, preview-only mirroring, WebRTC sending, stop/reconnect and error handling. No Focus implementation yet. |
| TLS | `tools/create_tls.py`: per-install CA and IP SAN server certificate; private key permissions and refusal to overwrite existing identity. |
| Fedora installation | `install.sh`, `tools/install_config.py`, `tools/install_launchers.py`, `packaging/fedora/`: dependencies, RPM Fusion Free camera akmod, user build, HTTPS/config, desktop launcher, boot camera helper, uaccess and scoped firewalld rules. |
| Tests | `tests/test_host.py`, `tests/test_install.py`, `tests/browser.mjs`, `tools/check_media_runtime.py`; workflow in `.github/workflows/ci.yml`. |

The Cargo workspace currently contains `apps/linux`. The proposed `crates/kagami-*` split and native Android companion have not been implemented.

## Evidence: passed versus pending

[Post-merge Actions run at `7217d27`](https://github.com/celestial-sora/kagami/actions/runs/37940929630) passed all four jobs. [PR #2 checks at `4d0f222`](https://github.com/celestial-sora/kagami/actions/runs/37940612911) also passed. Subsequent documentation changes did not alter the tested executable code.

| Check | Actual evidence |
| --- | --- |
| Host and installer | 22 Python tests passed. Host transport tests use real TLS/HTTP/WebSockets with a recording media backend. Installer tests cover real TLS creation/preservation, interface choice, launcher escaping, a no-change piped dry run and invalid helper inputs. |
| Browser | 7 Chromium scenarios passed with a synthetic camera and real browser VP8 peer connections: responsive layout, video exchange, switch, permission denial, pending-permission cancellation, protocol mismatch and host disconnect. The receiver is a browser fixture. |
| Native | ShellCheck, Desktop Entry validation and `cargo build --release -p kagami-linux` passed on Ubuntu 24.04. This proves build/link, not Fedora window behavior. |
| GStreamer | Real GStreamer 1.24.2 plugins and ICE port APIs passed. Three receiver teardowns freed their ICE agents with `G_DEBUG=fatal-criticals`. This does not exercise SDP negotiation with a phone, video decoding, V4L2 writes or OBS. |
| Hardware and install | **Pending:** complete installer execution on Fedora, kernel/Secure Boot/ACL/firewall behavior, physical Android certificate trust and camera behavior, Wi-Fi/USB media paths, native UI operation and phone → GStreamer → V4L2 → OBS. |

The previous authoring environment was Ubuntu without the local Rust/GTK/GStreamer toolchain or `/dev/video*`; relevant builds and real GStreamer API checks ran in GitHub CI. Inspect the CLI machine rather than inheriting those environment limitations.

## Next work: validate Phase 0 on Fedora

1. **Establish the environment.** Record Fedora release, running kernel, compositor/session, GStreamer, OBS, Android and browser versions. Check actual camera devices and Secure Boot state. Work from a clean feature branch; preserve unrelated local work.
2. **Exercise installation.** Use the existing installer, inspect failures and fix them in focused batches. Confirm matching kernel headers/akmods, normal-user camera access, the boot helper, actual selected interface and firewall rules. Re-running must preserve config/CA. Secure Boot enrollment/reboot is a pending human step, not an automatic success.
3. **Prove generated frames first.** Run doctor, choose the real Kagami loopback device, then `bash tools/test-pattern.sh /dev/videoN`. Confirm moving test bars inside OBS's V4L2 capture source. Stop the test producer before starting the receiver.
4. **Prove trusted phone HTTPS.** Verify the reachable host IP, certificate SAN, Android CA trust and camera permission on the actual browser. Transfer only `ca.pem` over a trusted channel. A QR or certificate-warning click-through is not proof of a supported secure context.
5. **Run the real receiver.** Start the reference host from the working checkout to isolate media/signaling problems from the GUI. Resolve actual SDP/ICE, plugin, caps, decoder and V4L2 failures. Then repeat through the native app.
6. **Exercise recovery.** Stop/start, camera switch, tab close, phone lock, Wi-Fi loss and reconnect while OBS retains the same source. Verify the no-signal slate and bounded latency instead of unbounded buffering or a crashed host.
7. **Record measurements.** Run 720p/30 for 15 minutes; record incoming/output FPS, stalls, CPU/RAM, negotiated caps and a repeatable glass-to-glass latency measurement. Test 1080p/30 and USB tethering, recording limitations and the actual media route.
8. **Update evidence and docs.** Complete [the hardware checklist](testing.md), record exact prerequisites/commands/results in `docs/validation.md`, fix installation/troubleshooting guidance and inspect Actions before delivery.

Minimum Phase 0 acceptance: **moving video from a physical phone camera appears in OBS through the actual Kagami V4L2 device over local Wi-Fi**, with reproducible setup and truthful evidence. Passing mocks, API checks or generated test bars alone cannot close that gate.

After that proof, continue in the agreed order: native host foundation/preview → camera and Wi-Fi/USB onboarding → phone-side Focus → Android MediaProjection screen/VTuber mode → release packaging and QA. Keep Android capture consent, foreground-service requirements and protected-content restrictions intact. Consult the full plan for milestone definitions.

## Useful commands

Run from the repository root as the desktop user. Follow [Fedora setup](fedora-setup.md) for system packages and [installation](installation.md) for the supported installer.

```bash
# Inspect before making changes; use a dedicated branch for implementation.
git status --short
git fetch origin

# Production-facing install entry point; first build needs Internet.
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash

# Inspect the setup plan without changing the machine.
bash install.sh --dry-run

# Test the actual GStreamer bindings, without a phone or camera device.
G_DEBUG=fatal-criticals PYTHONPATH=apps/host /usr/bin/python3 tools/check_media_runtime.py

# Use the installer-created config while running this checkout's host.
kagami_config_path="${XDG_CONFIG_HOME:-$HOME/.config}/kagami/config.json"
PYTHONPATH=apps/host /usr/bin/python3 -m kagami_host doctor --config "$kagami_config_path"
PYTHONPATH=apps/host /usr/bin/python3 -m kagami_host --config "$kagami_config_path"

# Run the checkout's native shell with that config and system Python.
KAGAMI_CONFIG="$kagami_config_path" KAGAMI_PYTHON=/usr/bin/python3 cargo run -p kagami-linux
```

The serve commands run until stopped; run one producer at a time. For manual configuration, start with `config.example.json`, replace its loopback IP/device with the real values, and follow [TLS setup](pairing-and-tls.md). `127.0.0.1` cannot pair a separate phone.

**Installer testing trap:** `install.sh` downloads the remote ref, default `main`; running a modified installer from a checkout does not install that checkout's unpublished app code. To test a published feature branch, set `KAGAMI_REF=<branch>` on the `bash` side of the command. Iterate on the reference host directly for unpublished media changes. Native overrides are `KAGAMI_ROOT`, `KAGAMI_CONFIG` and `KAGAMI_PYTHON`.

For relevant automated verification after dependencies are available:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m compileall -q apps/host tools
for script in install.sh packaging/fedora/kagami-camera-setup tools/test-pattern.sh; do
    bash -n "$script" || exit
done
shellcheck install.sh packaging/fedora/kagami-camera-setup tools/test-pattern.sh
npm install
npm run check
npx playwright install chromium
npm run test:browser
cargo build --release -p kagami-linux
git diff --check
```

Use Fedora equivalents for missing browser/system dependencies; the workflow's Ubuntu `apt` commands are not Fedora installation instructions. System Python needs the distribution's GI/GStreamer overrides and aiohttp; an isolated Python installation may not see them.

## Important boundaries and known limitations

- The app/build/media run unprivileged. The root boot helper creates/reuses one named loopback; it must not unload other cameras. Never use broad camera chmods, root GUI execution or a physical camera as an output.
- Auth: one-time 256-bit QR fragment token, five-minute pairing, eight-hour secure-cookie session, Origin validation, one sender, bounded events and rate limiting. Host stop/restart revokes in-memory credentials. Never publish live tokens, cookies, CA/server private keys or private configuration in logs/commits.
- Default HTTPS is TCP 8443; ICE is bounded to UDP 50000–50100. Rules are scoped to the selected private source subnet and configured destination IP. USB tethering requires its own reachable address/SAN/firewall scope; no ADB or raw USB transfer is involved.
- The installer targets DNF-based Fedora, not Atomic/Silverblue or containers. It builds from source, preserves settings/CA and installed versions, and returns code **10** for pending Secure Boot enrollment. Doctor/config/setup problems return **2**.
- Existing configs with an unavailable IP or mismatched certificate are preserved and rejected. Address migration and automatic certificate renewal remain unfinished. Server certificates last 90 days; CA certificates last one year.
- `configure_ice_ports()` repairs a sole-reference case when GI wraps webrtcbin's floating ICE agent. Do not remove the ownership guard without proving clean teardown on the target bindings; preserve the real weak-reference/teardown CI check.
- Browser cases must start in a new document, currently by navigating through `about:blank`. The pairing fragment is removed by the app; fragment-only navigation had retained previous test state and caused the two initial CI failures.
- Keep the output writer alive between phone sessions, use the slate when stalled/disconnected, and preserve bounded queues and generation isolation. Device availability after the host itself stops is different from phone reconnect behavior.
- Hardware acceleration, Focus, native Android screen capture, native preview/interface selection and final RPM/AppImage packaging are pending. A curl bootstrap exists; a packaged binary release does not.

## Git, CI and delivery discipline

Fetch before edits. Use focused local commits and a feature branch for implementation; integrate and verify before merging/pushing main. Avoid one main push per file. Never force-push, overwrite user work, or commit generated secrets.

`Checks` runs host, browser, native and media-api jobs. It cancels superseded runs for the same PR/ref and skips changes consisting only of `docs/**`, `README.md` and `AGENTS.md`. This file is under `docs/` to avoid a needless test run. Keep genuine failures visible. If required branch checks are introduced, revisit path filtering so documentation PRs do not wait indefinitely for skipped checks.

Inspect the actual Actions result/logs after source changes; workflow configuration or a successful push is not a passing test. Update `AGENTS.md` only with durable constraints, and `docs/validation.md` with actual test evidence. Deliver what changed, what passed, what still requires hardware/user action, and the final published Git version. Do not label v0.1 ready until its release criteria pass.

## Prompt for the next Codex CLI session

> Read AGENTS.md and docs/handoff.md, fetch current remote state and inspect this Fedora machine. Continue Kagami from the existing Phase 0 prototype. Start by validating the one-command installer, the real V4L2 test pattern in OBS, trusted Android HTTPS, and phone camera → GStreamer → Kagami Virtual Camera → OBS. Fix measured blockers in focused commits, preserve local-only authenticated transport and the curl installer, and verify relevant tests plus GitHub Actions before integrating to main. Do not replace V4L2 with Browser Source or claim hardware tests that were not performed. Record results in docs/validation.md, then advance through the implementation plan when the hardware gate passes.
