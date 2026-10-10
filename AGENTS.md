# Current maintainer direction: Ubuntu + Samsung Smart View

- The maintainer superseded Fedora/USB-first during this session: prioritize Samsung Smart View (Miracast sink) on Ubuntu. USB/authorized ADB Wi-Fi are fallback paths. Read docs/smartview-ubuntu.md.
- Smart View is an experimental MiracleCast control + RTP/MP2T/H264 decode adapter. Do not claim Galaxy interoperability from synthetic tests.
- Preflight only P2P-client/P2P-GO in the supported-interface-modes section of the selected PHY. P2P mentions in TX/RX lists are insufficient. Current authoring rtw88_8821ce does not advertise those modes.
- A fixed root-owned broker manages only the explicitly selected adapter via polkit; GUI/media remain unprivileged. EOF restores management. Never silently stop global networking or create passwordless sudoers.
- In Smart View mode require explicit consent for temporary selected-adapter disconnection. Test network restoration and real Galaxy discovery before advertising compatibility. No P2P-capable hardware is currently available.
- No PR for this migration; use the GitHub connector/Codex agent for publishing and integrate main once after CI. Attribute the contributor as celestail-sora using the linked celestial-sora account.

# Kagami V2 engineering context

- Current direction is docs/architecture-v2.md and docs/implementation-plan.md. Read docs/handoff.md, docs/receiver-audit.md and docs/validation.md before work. Historical V1 constraints below apply only to the retained legacy path where they conflict with V2.
- Prioritize Samsung Camera/TikTok visible screen → authorized ADB/scrcpy → shared crop/transform pipeline → real V4L2 output. No mandatory Android app, cloud/account, browser camera replacement or direct-camera substitution.
- V2 reference native desktop is Python/GTK4/PyGObject; Rust V1 is preserved. Keep a tested media boundary before migrating language/toolkit internals.
- Verify installed scrcpy version/help and use its documented V4L2 sink. Use two guarded named loopbacks. Never write into physical cameras or run the desktop as root.
- Keep bounded frame queues, persistent output/slate on disconnect and reliable child teardown. Stop must release capture immediately. Do not save screen images/video by default.
- Captured orientation is locked; crop settings are keyed by captured size and user-supplied app label. Do not promise automatic rotation/reconnect until implemented and tested.
- Smart View/Miracast is unverified research; Google Cast is research-only. ADB Wi-Fi requires explicit pairing/connection on a trusted private network and must never silently replace USB.
- Run legacy host/installer checks and receiver contract tests. Opt-in KAGAMI_TEST_GST=1 tests use real GStreamer with synthetic input; GTK smoke uses Xvfb. None proves Fedora/Android/OBS hardware acceptance.
- The maintainer explicitly requests one-command curl installation now. install.sh installs V2 on Ubuntu 24.04/26.04; historical Fedora V1 installer is install-v1.sh. Keep experimental hardware status explicit; preserve settings and never silently disconnect networking during installation. See docs/installation.md.
- The maintainer requests no PR for this migration; integrate after feature-branch CI and push main once. Contributor name requested: celestail-sora (or celestail-duck); GitHub account/repository owner is celestial-sora.

## Retained V1 engineering context

# Kagami engineering context

- For a new engineering session, read docs/handoff.md alongside the implementation plan and current validation record; the handoff is a dated snapshot, not a substitute for fetching the latest code.
- Linux hosts the local service; the phone sends video. OBS consumes a genuine V4L2 device named Kagami Virtual Camera.
- Work order follows docs/implementation-plan.md. Phase 0 hardware acceptance has not passed. Do not label this a working release until Fedora, Android and OBS are actually tested.
- Python/PyGObject is the Phase 0 reference integration; the native shell is Rust + GTK4/libadwaita. Migrate media into Rust only after validating the existing pipeline.
- No cloud signaling, TURN, accounts, CDN assets or mandatory Internet at runtime. Browser camera capture must use a trusted secure context.
- Never run the GUI as root, disable certificate checks, write into a physical camera, or include generated TLS/private configuration files in Git.
- v4l2loopback is a host prerequisite. AppImage/Flatpak cannot silently install its kernel module.
- Current media baseline is one video track, VP8, fixed output dimensions/FPS. Preserve the long-lived output writer and bounded queues on reconnect.
- Run Python auth/protocol tests and relevant client checks. Tests using recording media or synthetic camera inputs do not prove Linux/Fedora/phone hardware behavior.
- Verified in GitHub CI: 31 host/installer tests, 7 Chromium synthetic-camera scenarios, a native release build, ShellCheck/Desktop Entry validation, and real GStreamer plugin/ICE/teardown checks. Local Fedora installer rerun, three kernel module builds, native window startup, real V4L2 test frames, trusted local HTTPS and reference-host no-signal output also pass. See docs/validation.md for exact evidence. Physical Android media, OBS and kernel switching remain unverified.
- Browser scenarios must navigate to a fresh document between cases. The client removes its pairing fragment, so fragment-only navigation preserves previous module state and test tracks.
- The user's installation preference is one curl command. Keep install.sh idempotent, build/run the app as the desktop user, preserve settings/CA, and report Secure Boot enrollment as pending rather than a ready camera. Automatic setup currently targets DNF-based Fedora.
- ICE ports default to UDP 50000–50100; validate bounds and keep installer firewalld rules scoped to a private source subnet and the configured destination IP.
- configure_ice_ports repairs the sole-reference case when GI wraps webrtcbin's floating ICE object. PyGObject 3.56 can balance away a GI _ref() return; the guarded native g_object_ref restores the missing owner. Keep the real repeated-teardown/weak-reference check with fatal-criticals enabled when changing this compatibility boundary.
- Prepare a separate v4l2loopback module for every installed standard Fedora kernel of the host architecture. Retrieve missing exact development packages from repositories or the signed Fedora Koji archive with DNF signature checks enabled; verify each module's vermagic. Reuse RPM Fusion's update/boot hooks, preserve boot defaults, and report unsupported kernels/build failures explicitly.
- Keep commits focused, integrate work before pushing main, and avoid unnecessary main pushes. Fetch remote state before extending an existing branch.
- CI cancels superseded runs on the same PR/ref and skips documentation-only changes. Keep failures visible and verify code in a feature branch before merging. If required checks are introduced, revisit path filters so documentation PRs cannot wait forever on skipped checks.
