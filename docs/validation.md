# Validation record · 2026-10-09

## Fedora desktop checks

The CLI session now runs on the actual Fedora 44 Workstation desktop: GNOME/Wayland, GNOME Shell/Mutter 50.5, running kernel `7.2.8-200.fc44.x86_64`. Kernel `7.2.9-200.fc44.x86_64` and its matching `kernel-devel`/`kernel-devel-matched` are installed. Secure Boot is disabled. OBS Studio `32.1.1-3.fc44` is installed. Python is 3.14, PyGObject is 3.56.3, and GStreamer is 1.28.7.

Two measured blockers were fixed on `fix/fedora-kernel-bootstrap`:

- The original installer failed requesting unavailable development files for the running 7.2.8 kernel. Its new read-only selection correctly chooses the already installed 7.2.9 kernel with matching files. It stages the module/app setup and reports reboot pending (code 10), deferring camera loading and doctor until that kernel is running. Three additional inventory tests cover running-kernel preference, version ordering/incomplete development files, and rejecting older kernels, other architectures and development-only packages.
- The original `G_DEBUG=fatal-criticals` media API check aborted at ICE teardown. In this PyGObject version, `ice._ref()` left the native count at one; dropping the Python wrapper freed ICE while webrtcbin still held its pointer. A guarded native `g_object_ref` restores the missing owner. The real check now reconfigures each agent twice, exercises both destruction orders and confirms the agent is released after both owners are gone.

Passed locally on this Fedora machine:

- 25 Python host/installer tests with system Python; Python compilation and shell syntax checks.
- Seven Playwright/Chromium synthetic-camera scenarios and client JavaScript syntax checks. Playwright used its Ubuntu 24.04 fallback Chromium build on Fedora.
- `cargo build --release -p kagami-linux`, linked against installed GTK 4.22.5/libadwaita 1.9.4.
- ShellCheck 0.11.0 and Desktop Entry validation. ShellCheck was extracted from the Fedora RPM into a temporary user-owned directory without system installation.
- GStreamer 1.28.7 plugins, bounded ICE properties and three clean receiver/ICE teardowns with fatal criticals enabled.
- Installer dry run and read-only selection of the installed kernel/development pair.

Still pending on this machine: full privileged installer execution (sudo requires the desktop user's password), building/loading v4l2loopback and boot-service/ACL/firewall verification. Only the physical UVC camera's video0/video1 devices exist; no Kagami loopback is installed. Native window operation/visual inspection, generated frames in OBS, physical Android CA trust/capture, phone-to-GStreamer/V4L2/OBS, reconnects, 15-minute measurements and USB remain unverified. These local automated checks do not close Phase 0.

## Verified in the authoring environment

- Ubuntu 24.04 execution environment, Python 3.12, aiohttp 3.14.4, Node 24.
- 15 Python auth/protocol/TLS integration tests passed.
- Browser client and browser-test JavaScript syntax checks passed.
- Read-only doctor exits with an actionable missing-dependency/device report instead of starting a fake camera.
- One-command installer batch: 22 Python tests passed locally, including seven installer/configuration scenarios. They exercise actual local TLS generation and preservation, interface selection, literal launcher paths, a no-change piped dry run and invalid privileged-helper input. They do not run DNF, systemd, firewalld or kernel installation.

## GitHub CI evidence

- [Fedora kernel staging and modern PyGObject compatibility at `fb7727d`](https://github.com/celestial-sora/kagami/actions/runs/37946639315): all four PR #3 jobs passed. This includes 25 Python tests, seven Chromium scenarios, native release build/link, ShellCheck/Desktop Entry validation, and real GStreamer ICE checks covering repeated configuration and both teardown orders. This CI run uses Ubuntu 24.04; the Fedora results above were collected locally.
- [Installer and Actions checks at `4d0f222`](https://github.com/celestial-sora/kagami/actions/runs/37940612911): all four jobs passed. This includes 22 Python tests, 7 Chromium scenarios, ShellCheck, Desktop Entry validation, and an actual native release build/link on Ubuntu 24.04.
- GStreamer 1.24.2 found every required plugin, applied the ICE port limits, and freed the ICE agent after each of three receiver teardowns. `G_DEBUG=fatal-criticals` makes GLib critical messages fail the check. This checks real bindings/lifecycle, not negotiated phone media or V4L2 output.
- [Source checks at `0b5b52e`](https://github.com/celestial-sora/kagami/actions/runs/37935062062): all 15 host tests and 7 Chromium scenarios passed on Ubuntu 24.04.
- Chromium exercised responsive layout, a real VP8 synthetic-camera exchange, camera switching, permission denial, cancellation during pending permission, protocol mismatch and host disconnect. The receiver is a browser-local WebRTC fixture, not GStreamer.
- [Initial source checks at `1e443a4`](https://github.com/celestial-sora/kagami/actions/runs/37934155382): `cargo check --workspace` passed with GTK4/libadwaita development libraries. This checks compilation, not native window operation.
- Browser cases now start from a fresh document; fragment-only navigation had previously preserved tracks from the prior test and produced a false failure.

## Not verified here

This subsection describes the earlier Ubuntu authoring environment. The newer Fedora checks above supersede its dependency/build limitations, while the physical-device gate remains open.

- Rust/GTK execution and native visual inspection on Fedora. Local compilation was unavailable, but the GitHub compile check above passed.
- GStreamer decoding, GLib pipeline lifecycle, V4L2 writes and OBS integration: GStreamer/PyGObject and `/dev/video*` are absent.
- Physical browser behavior beyond the explicitly recorded Chromium synthetic-camera checks. Chromium is absent from the authoring environment; browser execution occurs in CI.
- Physical Android browser HTTPS/CA onboarding, actual front/rear switching, Wi-Fi/USB paths, capture behavior and latency.
- Fedora installation, kernel module/Secure Boot setup, native visual inspection and hardware acceleration.
- Fresh-Fedora execution of the complete curl installer, akmods/MOK enrollment, uaccess and firewalld behavior. These remain machine-dependent acceptance checks.

The GitHub workflow provides Python, browser and native-build checks. Workflow configuration alone is not evidence of passing checks; inspect the recorded run results.

The workflow cancels superseded runs on the same PR/ref and skips documentation-only pushes/PRs. Code changes keep all checks and failures visible. The two initial failed runs came from browser fixture state preserved by fragment-only navigation; the fixed tests start a new document. The passing runs above are the evidence of that correction.

**Phase 0 hardware acceptance remains open.** Focus, Android screen capture and final packaging were deliberately not advanced before that gate.
