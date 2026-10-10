# Runtime permissions and privacy

Kagami never runs its GUI/media as root. The V4L2 guard verifies loopback driver and Kagami label before opening either node; device locks prevent competing Kagami writers. Provisioning preflights both slots and never unloads another camera.

Smart View's fixed root-owned helper manages only the explicitly selected adapter after user consent, restoring management on EOF. AirPlay runs as an owned user process over the same LAN, with a loopback-only decoded-video bridge. Personal UxPlay startup options are ignored to prevent recording/pipeline overrides. ADB requires normal Android authorization and explicit pairing/connection.

No browser URL/QR pairing server remains. Screen content is not saved by default. Preview queues/logs are bounded; only explicitly saved crop settings are stored. AirPlay audio is disabled. Protected app surfaces may be black. Use sender-side approval prompts and a trusted local network; custom firewalls should scope receiver ports to that network/interface.

Stop/close terminate owned capture children and decoding; disconnect leaves black output until explicit reconnect/Stop. Physical phone, network-restoration and kernel-camera acceptance remain pending. See [validation](validation.md).
