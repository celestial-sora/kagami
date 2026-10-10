# Runtime architecture

The Ubuntu native GTK4 desktop controls transport adapters. Each adapter writes the identified **Kagami Screen Input** V4L2 loopback. A shared GStreamer processor publishes bounded source/processed previews and crop/rotation/mirror/fit/FPS output to a long-lived **Kagami Virtual Camera** writer. Disconnect selects black slate; Stop releases capture and all owned transport children.

- Smart View: fixed root-owned polkit network broker → MiracleCast sink → MPEG-TS/H264 RTP → unprivileged decoder → Screen Input.
- AirPlay: unprivileged owned UxPlay discovery/protocol child → loopback-only H264 RTP → unprivileged decoder/fixed 1280×720 canvas → Screen Input.
- ADB: authorized scrcpy documented V4L2 sink → Screen Input.

The browser camera, URL/QR pairing, TLS/WebRTC service and V1 Rust shell were removed at the maintainer's request. The device guard lives in `kagami_receiver.v4l2`; no V1 runtime dependency remains. Crop presets are local and explicitly saved only for verified ADB device identities.

`install.sh` installs the current receiver and fixed external helpers. Kernel-module/udev setup is privileged; GUI/media and external-source builds run as the desktop user. No cloud or default media recording.

The supplied [architecture-v2.md](architecture-v2.md) remains verbatim historical design input. Current maintainer transport/platform instructions and the implemented reference toolkit supersede conflicting portions. See [AirPlay](airplay-ubuntu.md), [Smart View](smartview-ubuntu.md), [validation](validation.md) and [testing](receiver-testing.md).
