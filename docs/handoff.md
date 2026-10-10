# Current handoff · 2026-10-10

Ubuntu native GTK4 receiver in `apps/receiver/kagami_receiver`: Samsung Smart View, AirPlay, USB and authorized ADB Wi-Fi feed a shared crop/rotation/mirror/fit/FPS pipeline and persistent real V4L2 camera output. The maintainer requests direct main integration after feature CI, no PR, contributor celestail-sora, and one-command curl installation.

The latest request adds AirPlay and removes the URL/QR connection system. Browser client, HTTPS/WebRTC host, QR-generating Rust shell, V1 installer, TLS/config helpers and obsolete tests/dependencies were removed. Reusable V4L2 identity guard moved into the current receiver; no V1 runtime imports remain. Existing user settings/previous installed app versions are preserved by updates, not used as new connection flows.

AirPlay uses separate UxPlay 1.73.2 at 4764e4619e8924f43601d778277fc9f0bf280597, Avahi, loopback-only H264/RTP and an unprivileged decoder normalized to a fixed letterboxed 1280×720 source canvas. It requires a same-LAN AirPlay sender, not Wi-Fi Direct. Native Galaxy Smart View remains Miracast. Audio and recording are disabled; personal UxPlay config is ignored. Stop reaps the owned process group. Phone identity/orientation preset tracking and Apple interoperability remain unverified.

Smart View uses the fixed polkit broker with explicit selected-adapter disconnection consent and EOF restoration. RTL8821CE/rtw88_8821ce currently lacks advertised P2P client/GO despite Windows Miracast history. Diagnose Linux driver options before concluding new hardware is necessary; no driver/network settings were changed here.

Default nodes: Screen Input video11, Virtual Camera video10; installer skips occupied physical slots and reuses identified nodes. The source/camera writer and device guards remain mandatory. Source entry: `bash tools/run-receiver.sh`; see [installation](installation.md), [AirPlay](airplay-ubuntu.md), [Smart View](smartview-ubuntu.md), [ADB](receiver-setup.md), [tests](testing.md), [validation](validation.md).

Hardware gates still open: real Apple/Galaxy discovery and negotiation, kernel camera output on Ubuntu, OBS/Discord, Stop/disconnect/network restoration and sustained latency/FPS. Synthetic media, GTK and backend discovery smoke do not close these gates. Archived V1 handoff/plan and supplied architecture are historical context; current instructions supersede conflicting workflows.

Installer update controls: commit comparison before downloads, recipe/platform/backend reuse, numbered progress, preserved `previous` app pointer, `kagami versions`/`rollback`, and explicit `--repair`. Release tags work today; release artifacts/default stable channel are future work. Rollback switches app payload only, not shared system packages/backends.

Latest installer correction: absence of P2P is now an optional Smart View warning with exit 0 when AirPlay/common prerequisites pass. New installs default to AirPlay without P2P. UxPlay v1.73.2 gets its missing stdio.h include, fixing the reproduced GCC 15 implicit-printf-declaration build error on Ubuntu 26.04. Live authorized installer verification is in progress.
