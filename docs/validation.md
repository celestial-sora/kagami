# Native window header correction · 2026-10-10

The maintainer's v2.0.0 screenshot shows an extra gray title strip and three blank system buttons. Broad .kagami button backgrounds replaced MacTahoe's window-control image assets while its image glyphs were transparent. The desktop now uses one Gtk.HeaderBar with the app branding/actions, and app CSS is scoped to kagami-content boxes that exclude native windowcontrols. Decoration colors stay readable for glyph-based themes; theme image backgrounds are preserved. The GTK smoke check exercises the native close button and validates header/control ancestry. Inspected under MacTahoe-Dark and Adwaita; all 70 contract/media/release tests pass locally. VERSION is 2.0.1 for a guarded stable patch; receiver backends/media behavior are unchanged. Contributor: celestail-sora.

# Mockup desktop UI · 2026-10-10

The native GTK4 desktop now follows the supplied purple Kagami camera mockup: AirPlay/Smart View source cards, connection status, stacked camera settings and preview options, a large source/crop preview and three-step usage panel. Start/Stop stay in the header. USB/ADB, receiver diagnostics, explicit adapter consent, framing and presets remain under Connection setup & framing controls; the processed camera preview has its own expander. The gear opens the setup controls. Mirror explicitly affects preview/output through the existing pipeline. Guide/safe-area switches are display overlays and do not modify camera pixels. The disconnected preview stays an honest empty state, and live source pixels replace it; no mock phone image or wallpaper is shipped. Existing approved app/launcher icons and saved preferences are preserved. Contributor: celestail-sora.

Local validation: all 68 contracts including opt-in synthetic GStreamer checks pass with fatal criticals, GTK/Xvfb checks pass, ShellCheck and diff checks pass. GTK checks cover source-card selection, overlays, saved settings/reopen, retained Start framing and Stop/close, with no real capture or network changes. The rendered window was visually inspected at 1360×1040 and the header remains visible at the smaller smoke-test size. Feature [CI 38059181882](https://github.com/celestial-sora/kagami/actions/runs/38059181882) passes all three jobs for code commit 6593a209, including actual receiver backend builds, synthetic media and GTK/Xvfb. Main integration uses the same executable tree with this documentation-only evidence update. Physical phone/OBS acceptance is unchanged by these UI checks.

# Desktop settings persistence · 2026-10-10

- The maintainer reports settings disappearing. GUI choices were not saved to installer settings, launcher arguments froze the installation defaults, and Start recreated the receiver with a full-screen crop. The desktop now saves/loads explicit transport, loopback nodes, output size/FPS, adapter, crop/aspect, rotation, mirror, fit/fill and preset label. Stop/Start retains framing; saved choices load before starting any transport.
- All **68** contracts/media tests pass with fatal criticals. Contracts cover migration of existing installer settings, Unicode labels, atomic failure preserving the previous file and cleaning temporary files, owner-only permissions, retained metadata, invalid values and explicit CLI overrides. The launcher is executed with literal special-character paths, then the settings file is changed and the same launcher passes updated values using only flags understood by older app payloads.
- Actual GTK/Xvfb checks verify retained framing across two Starts, reopened controls, debounced saves without Start, corrupted-file preservation, and no retained pairing code/disconnection consent. Smoke applications run as independent instances and assert their checks executed, preventing a pre-existing process from falsely satisfying the smoke test. All settings use temporary files; no host configuration/camera/network acceptance is performed. ShellCheck, compilation and diff checks pass.
- Existing device/orientation presets are preserved. Missing device presets no longer clear the last desktop framing. Wireless global settings do not imply phone identity, orientation tracking or per-wireless-device presets. No credentials, screen data, automatic capture state or network-disconnection consent are saved. Backend build recipes are unchanged, so the installer can reuse verified backends.

# AirPlay desktop audio · 2026-10-10

- The maintainer requests sound from the computer speakers so OBS can capture Desktop Audio, overriding the earlier audio-disabled instruction. The receiver previously passed `-as 0`; it now selects the user-session `pulsesink client-name=Kagami` output, while ignoring personal UxPlay configuration and retaining the local video bridge.
- The pinned backend builds successfully with bounded compressed input queues (64 buffers/two seconds, oldest dropped on stalls). A native harness compiles the actual audio renderer, pushes 1000 buffers into a stalled input without exceeding its limit, decodes eight non-silent synthetic ALAC buffers in memory, and confirms Stop returns the pipeline to NULL. It uses synthetic encoder codec metadata, not captured phone audio. AAC-ELD negotiation remains a physical-device check.
- All **64** contracts/media tests pass with fatal criticals, including missing audio plugins, runtime output errors, backend capabilities and owned-child teardown. Native RTP timestamps/lifecycle, actual Avahi advertisement with initialized fake audio output, GTK/Xvfb, ShellCheck, compilation and diff checks pass. A real user-session pulsesink reaches READY successfully without playing sound.
- Desktop/docs explain selecting Ubuntu’s output and the same OBS Desktop Audio device. No host audio selection, OBS configuration, privileged setup or network management is changed. Actual iPad sound through speakers, OBS mixer capture and A/V synchronization remain pending. Updating via the curl installer rebuilds the changed UxPlay recipe once; no media is recorded.

# 1080p camera output and held consumer · 2026-10-10

- With OBS holding video10, the actual GStreamer sink exposed only 1280×720. Requesting 1920×1080 failed negotiation. After the maintainer released the camera, a real named-loopback consumer read five complete 1920×1080 YUY2 frames (4,147,200 bytes each), and the maintainer explicitly confirms **1080p works**.
- The writer now opens the guarded output and queries supported dimensions before sending buffers or starting AirPlay. A blocked size reports how to deactivate the consumer and retry; controller cleanup releases ownership and leaves Start usable. Desktop controls explain the required order.
- All **62** contracts/media tests pass with fatal criticals, including complete synthetic 1080p frames, supported/pinned caps and partial-start cleanup. GTK/Xvfb verifies the 1080p selection reaches the receiver. ShellCheck, compilation and diff checks pass.
- A separate actual video10 check reads a full 1080p frame, keeps its consumer open while stopping the writer, rejects a 720p restart before any frame is emitted, then successfully restarts the writer at the held 1080p size. No screen/media files are recorded. AirPlay input remains 1280×720; this proves output dimensions, not native 1080p AirPlay input.

# AirPlay static-screen lifecycle correction · 2026-10-10

- The maintainer reports a static iPad screen eventually going black, while gaming remains connected for over ten minutes. Actual receiver logs show the previous four-second stale-video error; the controller also replaced media with slate after three seconds. These timers incorrectly equated missing changed frames with disconnect.
- AirPlay now retains the last processed frame at the selected camera FPS. Its owned patched UxPlay reports explicit RTP teardown, video TCP EOF (including a partial packet), final control-connection close, reset and the existing missed-feedback watchdog using fixed, immediately flushed events. Backend help advertises the required event capability; unpatched backends are rejected with installer guidance.
- All **59** contracts/media tests pass locally with fatal criticals. A real synthetic camera consumer reads ten identical generated frames despite a 600-second-old input timestamp, then reads black after protocol disconnect. Other transports retain their previous stale-frame behavior.
- The native check compiles actual UxPlay callbacks and links the real built libraries. It advances 600 logical one-second ticks with client feedback every two ticks, without additional media, then verifies teardown, control EOF, reset, lost feedback and actual loopback video TCP EOF. A fully buffered stdout pipe receives disconnect promptly. This is simulated protocol time, not ten minutes of wall-clock Apple casting.
- Actual pinned-backend build, RTP timestamp regression, Avahi advertisement/owned teardown, GTK/Xvfb, ShellCheck and compilation pass locally. Long static-screen acceptance on the physical iPad and further devices/reconnect/orientation remain open. No screen files were recorded.

# Real iPad → Kagami → OBS correction · 2026-10-10

- The maintainer confirms Start AirPlay is visible and Kagami is discovered on the same LAN by the iPad. Initial negotiation succeeded but neither preview nor camera showed video.
- Actual diagnostics reproduced videorate discarding decoded frames with CLOCK_TIME_NONE. The pinned UxPlay renderer only assigned PTS when videosink sync was enabled, bypassing it for RTP forwarding. The build now timestamps that path too. A harness compiles against the actual renderer and sends twelve synthetic H264 frames: unpatched v1.73.2 produces one constant RTP timestamp and fails; corrected source produces twelve advancing timestamps and passes.
- A second failure was reproduced after preview briefly appeared: v4l2sink renegotiated with OBS holding its buffers and failed S_FMT with EBUSY. The shared camera output now runs one fixed-format appsrc at selected FPS, swapping a bounded latest frame/black slate in memory. The loopback interval is corrected before caps probing; compressed H264 is never dropped by a leaky pre-decoder queue.
- The maintainer then explicitly confirms **video in both Kagami preview and OBS**. Runtime counters show live decoded/processed frames and roughly 30 output frames per second through the actual loopbacks. No screen/media files were recorded.
- All **54** contracts/media tests pass locally with fatal criticals, including identical camera caps across waiting/live/slate transitions. GTK/Xvfb, ShellCheck and compilation pass. Feature CI must pass before publication to main.
- Long sessions, other Apple devices, repeated reconnect/orientation handling, Discord, Galaxy/P2P and enabled Secure Boot remain unverified.

# Authorized Ubuntu 26.04 AirPlay installation · 2026-10-10

The maintainer explicitly authorized running the curl installer and correcting real failures while keeping AirPlay installable without P2P.

- Original main a71f0d8 failed building pinned UxPlay on GCC 15.2: video_renderer.c called printf without stdio.h. The fixed build adds only that missing declaration; normal compiler diagnostics remain enabled.
- Fixed feature d8e28d4 installs successfully on the actual Ubuntu 26.04 desktop with exit **0**, despite RTL8821CE/rtw88_8821ce lacking P2P-client/P2P-GO. AirPlay is available, Smart View is optional/unavailable, and the saved preferred transport is AirPlay.
- The installer reused unchanged installed MiracleCast, built UxPlay successfully, verified matching v4l2loopback module vermagic for 7.0.0-38-generic, and enabled/started the camera service. Secure Boot is disabled on this host; enabled-Secure-Boot acceptance remains pending.
- Named video10/video11 nodes pass the unprivileged identity guard. AirPlay doctor passes backend/discovery/decoder checks. The installed headless AirPlay receiver starts and stops normally with fatal criticals enabled and reaps its owned UxPlay child.
- A separate real V4L2 consumer reads five complete 1280x720 YUY2 black waiting frames from video10 while AirPlay listens. Frames stay in memory; no screen/media files are saved. This verifies waiting camera output, not actual Apple mirroring or OBS.
- All **52** contracts/media tests pass on the host. GTK/Xvfb verifies the initial AirPlay choice and controls; ShellCheck and compilation pass. [Feature CI 38034703869](https://github.com/celestial-sora/kagami/actions/runs/38034703869) passes all three jobs, including actual UxPlay/MiracleCast builds and Avahi discovery/teardown.
- Still pending: physical Apple authentication/negotiation/media, Galaxy/P2P/network restoration, OBS/Discord, enabled Secure Boot and post-reboot service acceptance. Host Wi-Fi management was not handed to MiracleCast.

Earlier records below are historical evidence from their stated batches.

Installer update checks additionally exercise unchanged-commit skips without download/sudo/builds, annotated-tag resolution, recipe/platform/binary reuse and reversible app rollback. Full installer operations remain tested with a fake system; host privileged installation is pending.

# AirPlay and removal of URL/QR validation · 2026-10-10

This batch adds experimental UxPlay AirPlay reception and removes the browser client, HTTPS/WebRTC pairing host, QR-generating Rust shell, V1 installer/TLS helpers and obsolete dependencies/tests. Reusable V4L2 guards now live inside the receiver. Historical evidence below describes removed code and is not current compatibility evidence.

- **52 current contracts/media tests**: default headless run passes 46 and skips six opt-in media tests. Real synthetic AirPlay H264/RTP portrait input passes, proving changing decoded frames, fixed 1280×720 canvas and black side borders. Receiver transform and Smart View RTP tests remain covered.
- AirPlay contracts verify UxPlay version/options, Avahi checks without P2P/network mutations, failure cleanup, stale stream, loopback-only forwarding, ignored personal config, audio/recording disabled, real child teardown and first-frame waiting.
- GTK/Xvfb checks mode visibility, AirPlay start without ADB selection, installer-selected adapter, crop and Stop/close. ShellCheck and compilation cover current code.
- CI builds pinned UxPlay/MiracleCast on Ubuntu 24.04 and verifies actual AirPlay mDNS advertisement/owned-process teardown. Consult the associated successful run before treating that configuration as evidence.
- **Still pending:** real iPhone/iPad/Mac authentication/negotiation/media, Galaxy/P2P, V4L2 kernel output/OBS, Ubuntu fresh installation/Secure Boot and Smart View network restoration. No physical phone or loopback nodes exist here. No host networking or system packages were changed by this development batch.

# Archived Ubuntu installer validation before AirPlay removal · 2026-10-10

The maintainer explicitly requested replacing the default installer now. `install.sh` installs V2 on Ubuntu 24.04/26.04; `install-v1.sh` preserves the previous Fedora implementation. It builds pinned MiracleCast unprivileged, installs fixed root-owned helpers/policy/license, provisions two named camera nodes and replaces the desktop/CLI launcher. Existing V1 configuration and receiver presets are preserved.

- Installer tests cover no-change piped dry run, exact kernel module verification, failed builds, Secure Boot/enrolled/missing-key paths, camera slot selection including dangling symlinks, settings preservation and literal launcher paths/arguments.
- A complete shell orchestration test uses fake package/root/network/build commands and temporary user directories. It verifies successful activation, no-P2P and MOK pending status, software failure preserving the previous active app, boot service behavior and temporary-file cleanup. It does not perform a privileged installation.
- Real receiver synthetic-frame tests and GTK/Xvfb smoke passed after the launcher/adapter changes. The CI receiver job builds and stages pinned MiracleCast on Ubuntu 24.04; consult its actual run result before claiming build success.
- **Still unverified:** fresh-host apt/DKMS setup, enabled Secure Boot enrollment/loading, real V4L2 provisioning on this Ubuntu host, Galaxy discovery/negotiation, broker network restoration and OBS streaming. The authoring adapter still lacks advertised P2P client/GO. No host network or system package/module settings were changed during this installer batch.

# Archived V2 validation before AirPlay removal · 2026-10-10

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
