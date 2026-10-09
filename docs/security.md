# Prototype security boundary

- The host binds one explicit local IPv4 address and uses TLS 1.2 or later. It never runs the GUI as root.
- Pairing uses a random 256-bit secret, a five-minute TTL, one-time exchange and bounded per-address rate limiting.
- Signaling requires the exact configured Origin and the secure session cookie. One active sender owns the media receiver; a second connection is rejected.
- Expired sessions close their WebSocket. Teardown completes before the sender slot is released, protecting the next connection from an old disconnect.
- Only one versioned video offer is accepted per connection. Messages and candidate queues have size limits. Audio tracks and multiple video tracks are excluded from this spike.
- The static router serves only the camera HTML, CSS and JavaScript. Private configuration, CA keys and source directories are never published by the service.
- No recordings, telemetry, external model downloads, public STUN/TURN, CDN requests, hosted accounts or relay infrastructure are implemented.
- The V4L2 writer checks the selected device identity before opening a media pipeline.

The local CA is a manual development bootstrap, not solved zero-setup onboarding. Keep its keys private and validate phone trust on each supported platform before announcing compatibility. The native QR/pairing URL is sensitive local UI/IPC; do not paste it into public logs or screenshots while active.

This is an initial boundary implementation, not an independent security audit. Physical TLS trust, ICE/firewall behavior and native packaging need validation before release.
