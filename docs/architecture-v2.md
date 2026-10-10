# Kagami (鏡) — Architecture v2

> **Status:** Architecture decision / implementation handoff  
> **Date:** 2026-10-10  
> **Targets:** Fedora Linux (Wayland), Android (especially Samsung Galaxy), OBS Studio, Discord  
> **Direction:** Receiver-first, local-first, universal Android screen-to-webcam bridge  
> **Decision:** Pivot V1 before completion; reuse reliable pieces rather than preserving the original browser-based streaming approach at all costs.

## 1. Product vision

Kagami turns whatever is **visibly rendered on an Android phone** into a Linux video source and an actual V4L2 virtual camera. Users keep their preferred camera applications, including **Samsung Camera**, **TikTok effects**, or other Android camera apps. Kagami does not need to reimplement their lenses, beauty effects, stabilization, or controls.

**Primary user experience:** Open a camera app on the phone → mirror/cast the screen to Fedora → select and crop the useful preview → expose it as `/dev/video*` → use it in OBS/Discord/other webcam consumers.

Also support full-screen phone mirroring for non-camera content.

### Product principles
- **Use existing camera apps:** no mandatory custom Android camera client for the core screen-mirroring workflow.
- **Local-first:** never require an account, cloud relay, or hosted server.
- **Native Fedora host app:** manages discovery, connection, preview, framing, and output.
- **Real virtual camera:** publish actual V4L2 video frames, not merely an OBS browser source.
- **Pluggable transport:** screen capture/cast protocols should be interchangeable without altering crop/output layers.
- **Honest capabilities:** each protocol's hardware, compatibility, and latency limitations are visible in the UI.

## 2. Architecture decision

Separate Kagami into **transport backends** and one shared video processing/output pipeline.

```text
Android device
  ├─ Samsung Camera / TikTok / any camera or screen app
  │     (rendered phone screen, including visible overlays)
  ├─ [A] scrcpy / ADB display mirroring (USB or ADB-over-Wi-Fi)
  ├─ [B] Miracast sink (Samsung Smart View; supported phones)
  └─ [C] Google Cast receiver (future, protocol/compatibility research)
                │
                ▼
       Kagami Transport Adapter
       (decode / normalized frames / metrics)
                │
                ▼
       Frame Processing Pipeline
       (crop / rotate / aspect fit / scale / fps / format)
                │
                ├────────────► Native preview + diagnostics
                │
                ▼
       V4L2 Virtual Camera Output
                │
                ├────────────► OBS Studio
                ├────────────► Discord
                └────────────► Browser / other webcam apps
```

### Critical distinction
- **scrcpy + ADB** is a pragmatic *first implementation path*, not a native Smart View receiver. It can use USB and Wi-Fi if the device is authorized via ADB.
- **Smart View / Miracast** requires a compatible Linux Miracast **sink**, working Wi-Fi Direct/P2P hardware and drivers, and may conflict with NetworkManager or current network topology.
- **Google Cast** is not automatically compatible with Miracast. Full Android screen-mirroring support in a custom receiver requires separate investigation and interoperability testing; do not promise compatibility merely from basic Cast receiver discovery or media playback support.
- **Direct camera capture** via scrcpy camera source (where supported by installed scrcpy and Android version) is a *separate optional mode*. It does **not** preserve Samsung Camera/TikTok's on-screen effects because it is not mirroring those apps.

## 3. Rollout priorities

### Phase 0 — Audit and preserve existing V1
1. Clone/pull latest `https://github.com/celestial-sora/kagami.git` and examine the current app, languages, tests, and workflows.
2. Record currently functional paths and known failures in an audit report; do not assume implementation state.
3. Create a migration branch (suggested `feat/receiver-first-architecture`). Preserve obsolete browser-streaming code in history or a separately named legacy module until replacement is proven.
4. Inspect GitHub Actions failures and separate existing CI defects from new architectural work.

**Exit:** reproducible build/test baseline and clearly scoped migration plan.

### Phase 1 — Functional USB screen-to-webcam MVP (highest priority)
1. Detect connected authorized Android devices via ADB.
2. Launch or integrate scrcpy screen mirroring via a **version-verified API/output path**. Confirm installed scrcpy supports the required V4L2/mirror functionality; avoid depending on undocumented internals.
3. Feed frames through Kagami's common processing pipeline and a working Linux V4L2 loopback device.
4. Offer live preview, interactive crop rectangle, framing presets (portrait, 16:9, 4:3), mirror, rotation, scale, and start/stop.
5. Verify OBS and at least one other V4L2-consuming application can open the output.
6. Test the actual Samsung Camera preview; test TikTok effects separately. Check whether camera preview, UI, and protected surfaces appear correctly.
7. Track FPS, dropped frames, estimated pipeline latency, device disconnects, and transport failures.

**Exit:** Samsung Camera → USB screen mirror → crop → `/dev/video*` → OBS, measured on real Android and Fedora hardware.

### Phase 2 — Wi-Fi via ADB/scrcpy
1. Pair/authorize ADB over network using supported Android wireless debugging or an explicitly authorized TCP connection.
2. Device discovery/reconnect UI and clear instructions for both Android and Fedora.
3. Compare Wi-Fi vs USB frame stability, latency, and recovery; do not silently switch networks.

**Exit:** wireless screen mirroring works without a mandatory Android Kagami app, on an authorized device and same reachable network.

### Phase 3 — Samsung Smart View / Miracast receiver
1. Prototype Miracast sink independently, evaluating MiracleCast and other maintained/compatible Linux sink implementations.
2. Preflight Wi-Fi Direct/P2P support, NetworkManager coexistence, necessary services, security, and firmware constraints.
3. Test whether Galaxy Smart View discovers Fedora as a display target and whether it can stream the Samsung Camera preview.
4. Wrap working sink with the same normalized-frame transport interface.
5. Expose precise compatibility failure messages rather than treating all Wi-Fi hardware as supported.

**Exit:** Verified Smart View connection from at least one Galaxy model on a documented Fedora hardware setup.

### Phase 4 — Google Cast compatibility research
1. Establish which Android versions and vendors support full-screen casting to third-party receivers.
2. Research licensed/proprietary protocol limitations and applicable open-source receiver libraries.
3. Build a compatibility proof of concept *before* advertising Google Cast support.
4. Only add a production transport if full-screen Android screen mirroring is proven; Cast media playback alone is insufficient.

**Exit:** documented feasibility result, either working integration or explicitly deferred unsupported target.

### Phase 5 — Optional direct-camera mode and polish
- Assess scrcpy camera capture independently of screen mirroring; label the loss of third-party app effects clearly.
- Camera preview crop presets per app/device orientation, saved locally.
- Packaging, clean install/uninstall, desktop entry, permissions guide, and single-command `curl` installer **only after** artifacts/install paths and integrity checks are dependable.
- Improve OBS/Discord interoperability, thermal/load behavior, and multi-device lifecycle.

## 4. Components and contracts

### 4.1 Transport interface
Each adapter must provide or negotiate:
- `start(config)`, `stop()`, `state`, and an explicit device identity;
- video frames or zero-copy buffers with width, height, pixel format, orientation, and timestamps;
- errors categorized as permission, connectivity, decoder, format, and unsupported hardware;
- transport stats (available FPS, dropped/late frames, and optional timestamps).

Do not tie UI widgets or V4L2 output to one transport implementation.

### 4.2 Frame pipeline
- **Crop:** manual draggable rectangle; persist per transport/app orientation if identifiable.
- **Aspect ratio:** 16:9, 4:3, 1:1, portrait, and freeform.
- **Transform:** rotate, horizontal flip, letterbox/fit/fill; predictable order of operations.
- **Formats:** negotiate formats required by V4L2 consumers; minimize avoidable encode/decode loops.
- **Overlay caveat:** crop removes UI **outside** the rectangle only. UI/filters drawn *inside* the crop remain in the output; Kagami must not claim to magically remove embedded UI.
- **Orientation:** detect/handle phone rotation and reassess saved crop safely.

### 4.3 Virtual camera
- Validate `v4l2loopback` presence, device accessibility, and permissions on Fedora.
- Present the actual selected `/dev/videoN` node and consumer test status.
- Handle resolution/frame-rate changes and reconnects without orphaning device writer processes.
- Avoid requiring permanent elevated privileges for the app runtime; clearly document module installation needs.

### 4.4 Fedora desktop application
- Connection mode picker: **USB Mirror** (recommended), **Wi-Fi Mirror**, **Smart View** (experimental once verified), **Google Cast** (research-only until proven).
- Device list and step-by-step connection diagnostics.
- Real-time preview with adjustable crop rectangle and common camera presets.
- Output configuration, metrics, and actionable error feedback.
- Avoid promising zero installation on the *Linux* host: native receiver and V4L2 dependencies may require packages/modules.

## 5. Testing and QA

**Required baseline environment:** Fedora on Wayland, Samsung Galaxy Android phone, physical USB cable, OBS Studio. Test Wi-Fi separately. Record exact hardware, Fedora version, Android/One UI versions, scrcpy version, and driver capabilities.

| Area | Test | Pass criterion |
|---|---|---|
| ADB | Authorized device identified | Correct serial; clear actionable error when unauthorized |
| USB mirror | Open Samsung Camera and mirror | Visible moving preview, no unexpected black/protected screen |
| Effects | Open TikTok camera effects | Visible effect in mirrored preview, if app permits mirroring |
| Crop | Crop shutter/controls outside target | V4L2 shows only selected crop |
| Aspect | Rotate phone and change preset | No wrong orientation or stretched frames |
| Virtual cam | Open device in OBS | Live video selectable and stable |
| Recovery | Disconnect/reconnect cable | No stuck writers; guided reconnect |
| Wi-Fi | Pair ADB and mirror | Reconnect and measurable frame rate |
| Miracast | Smart View discovers host | Tested hardware only; actual video received |
| CI | Build/unit tests without phone | Clean test pass and clear physical-device test separation |

**Important:** ADB/UI automation may be useful for QA, but some Android camera/casting permission dialogs require user confirmation. Never bypass protective prompts or access unrelated personal data.

## 6. Security and privacy

- All video traffic stays local; no cloud relay, telemetry, or hidden camera/background capture.
- Clearly show capture/streaming status and allow immediate Stop.
- Require explicit pairing/authorization, with no ADB exposure to untrusted networks.
- Never store captured video or screen images by default.
- Be transparent about apps that block mirroring, DRM/protected surfaces, and device-specific restrictions.
- Never auto-grant sensitive Android permissions or disable protections in order to force capture.

## 7. Engineering conventions and repository workflow

1. Read current repo state before changing any code, especially docs/build tooling/CI.
2. Develop and test in isolated commits or a feature branch. Commit coherent groups locally as necessary.
3. **Do not push `main` after each file/commit.** Once the complete integrated set has passed validation, push once as approved by the maintainer.
4. Do not delete legacy behavior until its replacement is verified; document migrations and breaking changes.
5. Keep hardware-dependent integration tests opt-in, with headless mocks for CI.
6. Summarize: architecture choices, files modified, tests run, unresolved compatibility constraints, and GitHub Actions state.

## 8. Non-goals for initial milestone

- Building a replacement camera app for Samsung/TikTok.
- Shipping an Android Kagami app as a mandatory dependency.
- Pretending Google Cast and Miracast are one protocol.
- Treating protected/DRM video as capturable.
- Perfect removal of UI overlays located inside the desired camera image.
- Claiming latency/FPS targets without empirical measurement.

## 9. First Codex implementation brief

> Audit the latest Kagami repository and pivot it to a receiver-first, pluggable transport architecture. Prioritize **USB ADB/scrcpy screen mirroring to a real V4L2 virtual camera**, with live preview and crop controls. This must preserve what the phone is displaying, including Samsung Camera or TikTok camera effects where screen mirroring allows. Do not replace the user's Android camera app. Keep Wi-Fi scrcpy as the next milestone, Miracast as an experimental transport, and Google Cast as research-only until proven. Fix broken baseline CI and include meaningful integration tests with documented manual checks. Keep changes on a feature branch or local commits; do not push to main incrementally.

---

**Decision summary:** Receiver-first / native phone-app-friendly / USB-screen-mirror-first / pluggable Miracast and eventual Google Cast / real V4L2 webcam on Fedora.
