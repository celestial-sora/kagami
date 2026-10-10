# V2 validation · 2026-10-10

Current target: **Ubuntu + Samsung Smart View**. Status: experimental source prototype; hardware acceptance remains open.

- Fresh audited baseline: c8f0ff3; latest executable baseline [Actions 37951587540](https://github.com/celestial-sora/kagami/actions/runs/37951587540) passed. No baseline CI defect found.
- All retained host/installer tests pass with aiohttp installed in a test-only runtime. Receiver contracts cover geometry, local presets, ADB authorization, explicit Wi-Fi mode, child reaping, ownership and writer persistence.
- **22 receiver tests pass** under system Python 3.14/GStreamer 1.28.2 with KAGAMI_TEST_GST=1 and G_DEBUG=fatal-criticals. Synthetic RGBA inputs prove crop, every quarter-turn, mirror order, fit/fill, actual transformed YUY2 output, black fallback and writer retention across processing restart.
- **8 Smart View tests pass**, including real local UDP RTP/MPEG-TS/H.264 moving-frame decoding. Broker/interface checks use mocks and do not prove actual P2P or network restoration.
- Real GTK4 window/crop/Stop/close smoke check passes under Xvfb, with Cairo integration. ShellCheck and Python compilation pass. Dependencies for local GUI/decoder tests were extracted into ignored .local/qa; no system network/module configuration was changed.
- Selected host adapter: wlo1 / phy0 / rtw88_8821ce; supported interface modes lack P2P-client/P2P-GO. smartview-doctor correctly rejects it. The current host also lacks installed MiracleCast/system TS parser plugins and /dev/video*.
- **Unverified:** Galaxy discovery/connect, Samsung Camera/TikTok surfaces, real loopback writes, OBS/Discord, P2P/Wi-Fi stability, broker restoration on Ubuntu, Ubuntu DKMS/Secure Boot, actual FPS/latency and Fedora compatibility. There is no physical phone or P2P-capable adapter for this session.
- V1 Rust/browser/media API and V2 Ubuntu-24.04 receiver checks are retained in GitHub CI; publication state is reported with the final delivery. A configured workflow is not evidence of a successful new run.

The supplied architecture-v2.md is preserved verbatim. The maintainer's later Ubuntu/Smart View priority overrides its Fedora/USB rollout. V1 evidence below is preserved historical context.

---

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

Following the user's installation of `dd27600`, the active app/launcher and HTTPS config are present, v4l2loopback 0.15.4 is installed, and a module exists for 7.2.9. The camera service is enabled but inactive while 7.2.8 is still running. The user's screenshot at 22:00 confirms the native Fedora window starts and reports the missing `/dev/video10`; this does not prove successful host/media operation.

Multiple-kernel installer batch on `fix/multiple-fedora-kernels`:

- Read-only inventory finds installed 7.2.7, 7.2.8 and 7.2.9, all x86_64. At the start of this batch only 7.2.9 has development files and a camera module.
- The signed Fedora Koji archive returns HTTP 200 for the exact 7.2.7 and 7.2.8 development RPMs. The downloaded 7.2.8 RPM passes `rpmkeys --checksig` (digests/signatures OK), has the expected package identity, and uses the same Fedora key as its installed kernel. This verifies the archive package, not installation or module compilation for 7.2.8.
- The installed akmods package has the kernel-install hook, kernel-specific service, enabled boot service and matching-development package dependencies. These existing paths are reused for future kernel updates.
- 31 Python tests pass. The new cases cover all installed kernel versions, architecture filtering, signed archive path construction, rejecting unsafe/unsigned metadata, preserving versions during exact-development transactions, enforced DNF signature checking, per-kernel akmods calls and detecting an incorrect module `vermagic` even when the builder reports success. These tests simulate package/build commands; they do not install packages or load modules.
- Shell syntax, ShellCheck 0.11.0 and `git diff --check` pass.

Real installer rerun at `93399aa`, completed without reboot:

- `bash install.sh` exits 0. DNF installs the exact signed 7.2.7 and 7.2.8 development packages from Koji; akmods builds their modules and reuses the existing 7.2.9 module. All three installed kernel-core/development pairs remain present. `modinfo -k <kernel> -F vermagic v4l2loopback` matches each of `7.2.7-200.fc44.x86_64`, `7.2.8-200.fc44.x86_64` and `7.2.9-200.fc44.x86_64`.
- The running kernel remains 7.2.8. v4l2loopback 0.15.4 loads there, creates `/dev/video10` named **Kagami Virtual Camera**, and the installer-created camera service reports active/exited with result success. Both the camera and akmods services are enabled. This verifies current activation, not a future boot or loading the other two modules.
- `getfacl -p /dev/video10` reports `user:sorachan:rw-`, group `video` read/write access and no world access. The unprivileged V4L2 identity guard and all nine doctor checks pass. SHA-256 hashes of the existing config and public CA certificate are unchanged before/after the installer. Existing scoped HTTPS/ICE firewall rules are reused; no phone traffic has tested them yet.
- `bash tools/test-pattern.sh /dev/video10` runs unprivileged. A separate real GStreamer `v4l2src` captures 60 YUY2 frames at 1280×720 with a 30/1 caps request in 2.06 seconds. Reading the raw capture in frame-sized chunks yields 59 distinct SHA-256 hashes, proving changing frames pass through the actual device. The test producer is stopped afterwards. No OBS visual check was performed.
- The checkout's reference host starts with the installed config and `G_DEBUG=fatal-criticals`. Its HTTPS landing page returns HTTP 200 using Python's normal certificate/IP verification and the installed CA. A real V4L2 consumer captures 60 full-sized no-signal frames from the host's persistent writer. Host SIGTERM/cleanup exits 0 without diagnostic stderr; `/dev/video10` remains present. No pairing token is published in the validation output.

Still pending: boot and switching between kernels (the user explicitly requested no reboot), Secure Boot enrollment/loading on an enabled system, a fresh-machine installation, and successful media through the native UI. Generated frames in OBS, physical Android CA trust/capture, phone-to-GStreamer/V4L2/OBS, phone firewall reachability, reconnects, 15-minute measurements and USB remain unverified. These checks do not close Phase 0.

## Verified in the authoring environment

- Ubuntu 24.04 execution environment, Python 3.12, aiohttp 3.14.4, Node 24.
- 15 Python auth/protocol/TLS integration tests passed.
- Browser client and browser-test JavaScript syntax checks passed.
- Read-only doctor exits with an actionable missing-dependency/device report instead of starting a fake camera.
- One-command installer batch: 22 Python tests passed locally, including seven installer/configuration scenarios. They exercise actual local TLS generation and preservation, interface selection, literal launcher paths, a no-change piped dry run and invalid privileged-helper input. They do not run DNF, systemd, firewalld or kernel installation.

## GitHub CI evidence

- [Main integration at `93399aa`](https://github.com/celestial-sora/kagami/actions/runs/37951587540): all four post-merge jobs passed; the published executable tree matches the tested PR #4 code.
- [Multiple installed Fedora kernels at `0b9c168`](https://github.com/celestial-sora/kagami/actions/runs/37951089129): all four PR #4 jobs passed. The inspected logs report 31 Python tests, seven Chromium scenarios, native release build/link, ShellCheck/Desktop Entry validation and the real GStreamer plugin/ICE/teardown check. Package installation and per-kernel driver builds are simulated in these installer tests; Ubuntu CI does not prove the Fedora kernel modules work.
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
