> **Installer update:** the maintainer explicitly requested one-command `curl … | bash` installation. `install.sh` now targets V2 on Ubuntu; historical Fedora V1 setup is `install-v1.sh`. Hardware acceptance remains open.

> **Maintainer update:** primary target is now **Ubuntu + Samsung Smart View**, ahead of USB. See [Smart View setup/status](smartview-ubuntu.md). The MiracleCast receiver prototype is integrated but physical Galaxy/P2P acceptance remains open; USB is a fallback. Earlier Fedora/USB rollout references below are historical context.

# Kagami V2 implementation plan

The supplied [Architecture v2](architecture-v2.md) supersedes the browser-first [V1 plan](implementation-plan-v1.md). Preserve working V1 behavior until hardware verification proves the replacement.

1. **Audit/baseline:** completed source/CI audit in [receiver-audit](receiver-audit.md); preserve V1 tests and installer.
2. **USB screen-to-webcam:** V2 reference desktop, scrcpy transport, shared frame processing and actual V4L2 writer are implemented in source. **Hardware gate is open:** Samsung Camera → USB → crop → V4L2 → OBS and a second consumer on Fedora/Wayland.
3. **Authorized Wi-Fi:** explicit Android Wireless debugging pair/connect plus the same adapter/output are implemented in source. Prove latency, stability, disconnect and explicit reconnect on the same trusted network.
4. **Miracast:** independent Linux sink research, P2P/driver/NetworkManager preflight and at least one documented Galaxy/Fedora setup before integration or advertising support.
5. **Google Cast:** full Android screen-cast feasibility/interoperability research; media playback/discovery alone does not satisfy this milestone.
6. **Polish/package:** improve Rust integration if justified by validated media behavior; direct-camera mode must clearly explain the loss of third-party app effects. Complete V2 install paths/integrity checks before replacing the legacy curl installer.

Use [receiver setup](receiver-setup.md), [physical testing](receiver-testing.md) and [validation](validation.md). Keep hardware tests opt-in. Commit/push integrated changes after validation, without incremental main pushes. For this migration the maintainer explicitly requested direct integration without a PR.
