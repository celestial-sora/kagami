# Kagami engineering context

- Linux hosts the local service; the phone sends video. OBS consumes a genuine V4L2 device named Kagami Virtual Camera.
- Work order follows docs/implementation-plan.md. Phase 0 hardware acceptance has not passed. Do not label this a working release until Fedora, Android and OBS are actually tested.
- Python/PyGObject is the Phase 0 reference integration; the native shell is Rust + GTK4/libadwaita. Migrate media into Rust only after validating the existing pipeline.
- No cloud signaling, TURN, accounts, CDN assets or mandatory Internet at runtime. Browser camera capture must use a trusted secure context.
- Never run the GUI as root, disable certificate checks, write into a physical camera, or include generated TLS/private configuration files in Git.
- v4l2loopback is a host prerequisite. AppImage/Flatpak cannot silently install its kernel module.
- Current media baseline is one video track, VP8, fixed output dimensions/FPS. Preserve the long-lived output writer and bounded queues on reconnect.
- Run Python auth/protocol tests and relevant client checks. Tests using recording media or synthetic camera inputs do not prove Linux/Fedora/phone hardware behavior.
- Verified in GitHub CI: 15 host tests, 7 Chromium synthetic-camera scenarios, and native GTK compilation. See docs/validation.md for run evidence. Native execution and the complete GStreamer/V4L2/Android/OBS path remain unverified.
- Browser scenarios must navigate to a fresh document between cases. The client removes its pairing fragment, so fragment-only navigation preserves previous module state and test tracks.
- Keep commits focused, integrate work before pushing main, and avoid unnecessary main pushes. Fetch remote state before extending an existing branch.
