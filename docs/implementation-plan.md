# Current implementation plan

The native receiver and one-command Ubuntu installer support experimental Smart View and AirPlay plus ADB fallbacks. The browser URL/QR system is removed by explicit maintainer request; keep the supplied architecture document verbatim as historical input.

1. Validate shared source/crop/output, bounded previews, device guards and Stop/black-slate behavior.
2. Verify Smart View with an appropriate Linux P2P driver and actual Galaxy discovery/negotiation/restoration.
3. Verify AirPlay with an actual iPhone/iPad/Mac on the same LAN, including rotation/crop changes and reconnect.
4. Run the [hardware acceptance checklist](receiver-testing.md): real V4L2, OBS/second consumer, disconnect, Stop and sustained latency/FPS.
5. Verify fresh Ubuntu install, DKMS and Secure Boot enrollment/loading. Keep installer status explicit and preserve user settings.

Publish through the GitHub connector after feature-branch CI, then integrate main once without a PR. Synthetic tests and backend advertisements are not phone acceptance. See [validation](validation.md) and [handoff](handoff.md).
