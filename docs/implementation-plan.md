# Kagami (鏡) — Implementation Plan

> **Project #17** · Linux-native phone-to-virtual-camera bridge
> **Status:** Planning / Ready for engineering kickoff
> **Prepared:** 2026-10-09
> **Primary targets:** Fedora (Wayland), Android, OBS Studio
> **Principle:** Local-first · No cloud relay · Actual Linux Virtual Camera

## 1. Product vision

**Kagami** turns a phone into a camera or screen-streaming source for Linux. The Linux native application hosts a local pairing/streaming service; a phone joins as the **client** over local Wi-Fi or USB networking, and sends video to the Linux host. The host publishes that video to a **real V4L2 virtual camera**, selectable in OBS Studio, Discord, or any other compatible app.

The primary use cases are:

1. **Webcam Mode:** phone front/rear camera → Linux `Kagami Virtual Camera`.
2. **Kagami Focus:** Center Stage-style auto-framing (face/person detection, smoothly keeping subject centered).
3. **VTuber / Screen Mode:** phone renders the VTuber app locally and captures its screen → Linux virtual camera, reducing Linux-side rendering work.

**Non-negotiable:** The output must be an actual Linux camera device, **not** an OBS Browser Source, URL stream pasted into OBS, or an OBS virtual-camera-only workaround.

## 2. Decisions already made

| Area | Decision |
| --- | --- |
| Product name | **Kagami (鏡)** |
| Architecture | **Linux is host/server; phone is streaming client** |
| Platform order | **Linux + Android first**; evaluate iOS and Windows later |
| Linux UI | Native desktop app using **Rust + GTK4/libadwaita** |
| Phone onboarding | Display locally reachable URL and QR code in Linux app |
| Network | Local Wi-Fi and USB networking; no central relay, account, or mandatory Internet |
| Browser client | Mobile web client for camera permission and video sending |
| Mobile native client | Android companion for full-device screen capture and reliable background integration |
| Streaming | Prefer **WebRTC**; validate actual end-to-end pipeline in Phase 0 |
| Virtual camera | **v4l2loopback/V4L2** device fed by receiver's decoded frames |
| Integration | OBS should see `Kagami Virtual Camera` under Video Capture Device (V4L2) |
| Visual direction | Anime-minimal, clean desktop utility rather than a character-centric UI |

### Clarification: “Server” does not mean cloud

The native Linux application runs a **local service on the user's computer**. The phone opens its URL (e.g., `https://192.168.x.x:<port>` **only when TLS is configured and trusted**) and pushes video to that machine. Both devices communicate directly over LAN or a USB network link; the system does not need a hosted server on the public Internet.

## 3. High-level architecture

```text
┌───────────────────────────── Linux computer ────────────────────────────┐
│ Kagami native app (Rust + GTK4/libadwaita)                              │
│                                                                         │
│  Local control service ── Pairing UI / QR / session authentication       │
│          │                                                              │
│          ├── Web client (camera capture) served over trusted HTTPS      │
│          └── Signaling (WebRTC offer / answer / ICE)                    │
│                         │                                               │
│                Media receiver / decoder                                 │
│                         │                                               │
│              Frame normalization (format, size, FPS)                    │
│                         │                                               │
│            GStreamer → v4l2loopback → /dev/video*                       │
│                         │                                               │
│                 OBS / Discord / browser                                 │
└─────────────────────────┬───────────────────────────────────────────────┘
                          │  local Wi-Fi or USB tethering
                          │  (direct media connection)
            ┌─────────────┴────────────────────────┐
            │                                      │
  ┌─────────▼─────────┐                  ┌─────────▼────────────┐
  │ Phone browser     │                  │ Android companion    │
  │ Camera + preview  │                  │ Camera / screen      │
  │ Auto-framing      │                  │ MediaProjection      │
  │ WebRTC sender     │                  │ Hardware encoding    │
  └───────────────────┘                  └──────────────────────┘
```

### Network and connection flow

1. User launches **Kagami Host** on Linux.
2. Host initializes/checks V4L2 loopback device, local signaling endpoint, and a pairing session.
3. Native UI shows QR code and local URL with a short-lived pairing token; device discovery may use mDNS as a convenience, not a dependency.
4. Phone connects via Wi-Fi LAN or a USB network interface and pairs with the host.
5. Phone grants camera permission or (Android companion only) screen-capture permission, then streams encoded video via WebRTC.
6. Linux receives, decodes, converts frames to a negotiated format, and writes them into the virtual camera.
7. OBS selects **Video Capture Device (V4L2) → Kagami Virtual Camera**. No media URL needs to be entered in OBS.
8. Disconnect/reconnect preserves the device where feasible and displays a clear no-signal frame rather than blocking the UI.

## 4. Technical components

### 4.1 Linux host

- **Language/UI:** Rust + GTK4/libadwaita.
- **Media pipeline:** GStreamer and its relevant WebRTC / RTP / video-conversion modules; choose specific Rust integration after Phase 0 verification.
- **Virtual output:** `v4l2loopback` kernel module and V4L2 writer. Prefer a stable device name and `exclusive_caps=1` where needed for compatibility.
- **App responsibilities:** pairing, start/stop host, stream preview, device status, selected mode, resolution/FPS, bitrate estimate, disconnect/reconnect, logging.
- **Privilege boundary:** Keep host unprivileged. If kernel module loading/configuration needs elevated rights, use a narrowly scoped setup/install procedure or privileged helper, **not** a permanent root-running UI.
- **Packaging:** Begin with Fedora RPM or a documented Fedora developer install; investigate AppImage/Flatpak later. A sandboxed package may need host device access and cannot silently load kernel modules.
- **Secure Boot:** Document limitations of out-of-tree `v4l2loopback` kernel modules and available distribution-specific signing/setup paths.

### 4.2 Phone web client (camera mode)

- Responsive mobile page served from Linux host, designed for touch.
- `getUserMedia()` front/rear camera selection, preview, permission guidance, portrait/landscape orientation handling.
- WebRTC sender + local signaling.
- Kagami Focus: face detection + smooth digital crop before sending (prototype MediaPipe web/WASM or another on-device solution; measure thermal/battery impact).
- Controls: start/stop, switch camera, flip preview, resolution/FPS preset, auto-framing toggle, connection state.
- **Security requirement:** Mobile browsers typically require a **secure context** to use camera APIs. An arbitrary plain `http://<LAN-IP>` page does **not** qualify. Design a trusted HTTPS bootstrap/pairing method and verify it on target Android browsers. Do not treat self-signed HTTPS without certificate trust as a solved UX.

### 4.3 Android companion (screen / VTuber mode)

- **Android-first:** Kotlin + Jetpack Compose.
- Use Android `MediaProjection` for screen capture; follow Android version-specific user consent, foreground-service, token lifetime, and stop/resume requirements.
- Hardware video encoding via `MediaCodec` (or a compatible abstraction); prioritize H.264 compatibility first.
- Reuse host signaling/auth/session conventions; do not assume browser screen-capture APIs work on Android.
- The application cannot bypass `FLAG_SECURE`, app-level capture blocking, DRM restrictions, or audio-sharing restrictions.
- Screen streaming normally runs while the selected VTubing app is in the foreground; Android companion handles capture through approved system APIs, not unauthorized access to another app's video buffers.
- Optional alpha-background workflows require explicit implementation; MVP should initially support chroma key / solid-background workflows rather than assume transparent screen capture.

### 4.4 Connectivity

- **Wi-Fi:** Same LAN, or phone hotspot where the computer can reach the phone's network.
- **USB:** USB tethering is the initial supported method, creating a network link between devices. The host must choose the reachable interface/IP; do not assume the Wi-Fi URL works over USB.
- **WebRTC:** No public TURN or cloud signaling. Use host-local signaling and direct ICE candidates; validate local-network permissions and browser behavior, and handle address changes.
- **Pairing/security:** Short-lived QR/pairing token, secure session transport, explicit approval and/or trusted-device pairing, session expiration, and protection against unexpected LAN viewers/stream injectors. Bind local interfaces intentionally; no Internet-facing port forwarding.

## 5. MVP specification

### In scope for the first usable release

- Linux native window that starts/stops a local host.
- QR code / usable URL for pairing a phone on the same LAN.
- Secure camera capture via mobile browser.
- Stream phone video to Linux over Wi-Fi.
- Actual V4L2 virtual camera, visible and selectable from OBS.
- Basic settings: front/back camera, source resolution/FPS, connection status, frame diagnostics.
- Graceful disconnect and easy reconnect.
- Documented manual USB tethering workflow.

### Explicitly out of scope for first MVP

- iOS-specific native companion.
- Cloud relay, accounts, hosted signaling, remote Internet streaming.
- Native Android screen capture and VTuber mode (planned milestone after webcam pipeline is reliable).
- Guaranteed 4K/60 FPS, perfect background transparency, audio mixing, or complex effects.
- Automatic driver installation without the necessary system permissions.

## 6. Delivery phases and acceptance criteria

### Phase 0 — Feasibility spike / end-to-end proof of concept

**Goal:** Prove a real camera device can receive phone video, before investing in polished UI.

Tasks:

- Validate `v4l2loopback` setup on target Fedora/Wayland kernel.
- Push generated test frames to a V4L2 device using GStreamer; verify OBS can select and display them.
- Build a minimal secure phone-camera test sender and Linux receiver.
- Choose working WebRTC-to-GStreamer decoding and V4L2 writing pipeline; record working codecs, pixel formats and caps.
- Measure baseline end-to-end latency, FPS stability, CPU, and reconnection behavior.
- Record browser HTTPS/trust onboarding and USB tethering proof-of-connectivity.

**Definition of done:** A phone camera produces moving video inside OBS via a genuine V4L2 source, over local Wi-Fi. No Browser Source or pasted streaming URL. Document exact commands and prerequisites.

### Phase 1 — Linux native host foundation

Tasks:

- Rust workspace and GTK4/libadwaita window.
- Split core media engine from GTK presentation layer.
- Start/stop local service and signaling.
- Setup/status checks for camera device and driver.
- QR pairing UI, connection/permission errors, basic diagnostics.
- Stable device lifecycle on disconnect/reconnect.

**Definition of done:** Host can be started and monitored fully from GUI, without routine terminal usage after setup.

### Phase 2 — Camera client + USB/Wi-Fi usability

Tasks:

- Responsive browser client with camera switch, preview, controls.
- Trusted HTTPS solution and first-time onboarding guide.
- Auto-select/recommend correct host LAN address and show interfaces.
- Reconnect flows and orientation/resolution handling.
- USB tethering verification and interface selection.

**Definition of done:** A new user can pair on supported Android browser, use Wi-Fi or USB tethered networking, then select the virtual camera in OBS.

### Phase 3 — Kagami Focus (Center Stage-style)

Tasks:

- Implement phone-side face detection and face bounding boxes.
- Add framing algorithm with smoothing/dead zone, zoom limits, edge-safe crop, and lost-face fallback.
- Reframe for 0/1/multiple faces with predictable rules.
- Add toggle and optional crop/zoom sensitivity control.
- Profile mobile heat, dropped frames, and latency with feature on/off.

**Definition of done:** Subject stays centered during ordinary movement, without jittery cropping; no significant regression outside agreed measured budget.

### Phase 4 — Android screen / VTuber mode

Tasks:

- Kotlin companion with pairing and MediaProjection capture.
- Encode video on phone and deliver to existing host session receiver.
- MediaProjection consent, foreground service/notification and cleanup.
- Separate Camera and Screen modes in UI.
- Document capture limitations; demonstrate with a compatible VTubing app.
- Test OBS chroma key or matching solid background workflow.

**Definition of done:** Compatible VTubing app runs/rendered on phone, while OBS sees its captured screen from `Kagami Virtual Camera` on Linux. No Linux-side VTuber renderer required.

### Phase 5 — Quality, release, documentation

Tasks:

- Fedora RPM (and subsequent packaging evaluation), installer/setup docs.
- CI: lint, formatting, Rust tests, Android build, browser-client checks.
- Host service and client compatibility tests, protocol version negotiation.
- Security review and permissions/privacy UI.
- Recovery paths for no camera, disconnected device, untrusted HTTPS, unavailable driver, blocked screen capture.
- README, quick start, troubleshooting, architecture and release checklist.

**Definition of done:** Fresh Fedora installation instructions and a repeatable demo pass with Android and OBS, with limitations clearly documented.

## 7. Suggested repository structure

```text
kagami/
├── README.md
├── LICENSE
├── Cargo.toml                    # Rust workspace
├── apps/
│   ├── linux/                    # GTK4/libadwaita native host UI
│   ├── web-client/               # Camera browser client
│   └── android/                  # Native phone companion (later phase)
├── crates/
│   ├── kagami-core/              # Host state, sessions, configuration
│   ├── kagami-signaling/         # Local pairing and WebRTC signaling
│   ├── kagami-media/             # Receiver, decoder, caps, frame pipeline
│   └── kagami-v4l2/             # Virtual camera management/output
├── packaging/
│   └── fedora/
├── docs/
│   ├── architecture.md
│   ├── security.md
│   ├── pairing-and-tls.md
│   ├── usb-tethering.md
│   ├── testing.md
│   └── troubleshooting.md
└── .github/workflows/
```

*The layout is a starting point; alter it if the Phase 0 integration spike demonstrates a better maintainable boundary.*

## 8. Engineering requirements

### Video and performance

- Initial compatibility target: **720p/30 and 1080p/30**; 60 FPS is stretch, not a launch promise.
- Hardware H.264 encoding when supported. Normalize frames and document negotiated V4L2 pixel formats (e.g., YUYV/NV12 as supported by the pipeline).
- Provide metrics for incoming FPS, output FPS, frame drops, bitrate, queue delay, and estimated glass-to-glass latency measured by repeatable tests.
- Prefer frame dropping over unbounded buffering under overload to avoid spiraling delay.
- Phone-side Focus should not require Linux GPU inference.

### Reliability

- Never crash host on browser tab close or phone lock.
- On reconnect, renegotiate stream without forcing OBS source recreation when possible.
- Avoid hanging camera consumers when no frames arrive; use no-signal/slate frames where compatible.
- Detect device/module absence and show actionable setup instructions.

### Security and privacy

- No recordings or upload by default.
- No remote analytics, tracking, accounts, or telemetry by default.
- Only pair/stream after user initiation. One-time/short-lived pairing, host-side authorization and session revocation.
- Use secure transport for sensitive permissions and signaling; never silently disable certificate verification.
- Restrict camera/frame access to the active local session. Do not allow arbitrary LAN participants to inject streams.

### UX

- Linux native UX: large preview, clearly labeled **Host status**, **Pair phone**, **Camera / Screen mode**, **Virtual Camera status**, **Stop stream**.
- Keep terminal-free day-to-day usage after installation; explain one-time driver setup cleanly.
- No excessive animation, always keep errors understandable.
- Mobile page should remain usable at phone portrait widths.

## 9. Testing matrix

| Scenario | Expected result |
| --- | --- |
| Fedora Wayland + OBS | `Kagami Virtual Camera` appears as V4L2 capture device and displays live frames |
| Android Chrome camera client on Wi-Fi | Permission → preview → streaming success with authorized secure context |
| Phone camera front/back switch | Stream continues or renegotiates cleanly |
| USB tethering | Host and phone connect locally without public network dependencies |
| Pause/lock client | No crash; host reports disconnected/paused correctly |
| Wi-Fi interruption/reconnect | UI recovers and device state remains sane |
| Missing `v4l2loopback` | Actionable error; no silent failure |
| Secure Boot / kernel mismatch | Clear diagnosis and documented recovery |
| Wrong pairing token | Connection rejected |
| Focus movement test | Smooth crop, bounded zoom, safe fallback when face lost |
| Android Screen Mode (Phase 4) | VTuber app's allowed screen content appears via same V4L2 camera |

## 10. Risks and constraints to resolve early

1. **Browser HTTPS bootstrap:** Camera access needs a trustworthy secure context; local-IP TLS trust and QR onboarding can be the biggest UX blocker. Prototype this before polishing the app.
2. **Virtual device and kernel compatibility:** `v4l2loopback` is an out-of-tree kernel module; packaging, Secure Boot, and Fedora kernel updates require attention.
3. **WebRTC interoperability:** Rust media, GStreamer WebRTC, browser SDP/ICE, and V4L2 caps negotiation need an early tested vertical slice.
4. **USB is a network link in v1:** USB tethering is simpler than implementing native USB transfer; it may require enabling tethering explicitly on Android.
5. **Capture policy:** Screen capture on Android requires user consent and is restricted by protected content/apps. Browser capture cannot be relied on for arbitrary Android screen sharing.
6. **Thermal/CPU tradeoffs:** Camera + on-device ML + video encoding can tax phones; profile and gracefully reduce workload.
7. **OBS format compatibility:** Some consumers need particular caps or `exclusive_caps`; verify actual OBS device detection and long-lived capture.

## 11. Milestone ordering and work discipline

**Work order:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5. If Phase 0 encounters a blocker, prove an alternate implementation before committing to broader development.

For repository work:

- Fetch current remote state before changes; create a dedicated feature branch when collaborating.
- Implement in focused batches. Run the relevant tests after each batch.
- Make useful intermediate Git commits; avoid pushing `main` for every file/change.
- If GitHub remote and permission are available, open a PR or make a single main push only after integrated tests and review, according to repository policy.
- Never claim a hardware test passed unless it was actually performed on the required device/environment.

## 12. Execution brief for GPT Work

> **Goal:** Build the open-source project **Kagami (鏡)**: a Linux-native phone webcam/screen bridge, with a local Linux host, an Android phone/browser as streaming client, and actual V4L2 virtual-camera output for OBS. **Do not replace Virtual Camera with Browser Source or a stream URL.**
>
> Start by creating the repository skeleton and completing **Phase 0**. Choose practical Rust, GStreamer, V4L2, WebRTC, and HTTPS components based on tested compatibility. Implement a reproducible vertical slice in which phone camera video reaches OBS through `Kagami Virtual Camera`; document any machine/device-dependent prerequisites. Next, proceed through the phases in this plan if the environment supports them. Build a native GTK4/libadwaita Linux host and responsive phone camera browser client, then Center Stage-style on-phone tracking and an Android MediaProjection client for VTubing/screen share. Respect a local-only, authenticated and secure transport architecture; avoid any mandatory cloud infrastructure.
>
> Deliver code, tests, setup documentation, a list of known limitations, and a succinct report of what actually works versus what requires testing on Fedora/Android hardware. Keep intermediate commits; minimize unnecessary production/main pushes. If no connected repository is supplied, initialize the project locally and report the exact repo/files and next publication step rather than assuming a remote exists.

## 13. Release definition

**Kagami v0.1 is successful when:**

- A Linux native app hosts the connection.
- A phone joins over a local connection using QR/URL and streams camera video.
- Linux exposes a persistent, usable **Kagami Virtual Camera** through V4L2.
- OBS receives live video by selecting this device, without entering any video URL.
- The README explains both local Wi-Fi and initial USB-tethering workflows, security/trust bootstrap, known restrictions and setup prerequisites.

**After v0.1:** add Kagami Focus, Android screen-sharing/VTuber support, and stronger packaging/integration in separately testable releases.
