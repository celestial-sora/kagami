# Troubleshooting

| Symptom | Check |
| --- | --- |
| Browser cannot request camera | Use the correct HTTPS URL, trusted CA and matching IP SAN; check camera permission. |
| Phone cannot open URL | Use the computer's reachable interface address. A separate phone cannot use the computer's 127.0.0.1 address. |
| Browser pairs but video stalls | Inspect local ICE/firewall/mDNS candidate interoperability and GStreamer/libnice logs. No relay is configured. |
| Import of `gi` fails | Use the distribution's system Python with PyGObject installed; run doctor in that same interpreter. |
| Missing `webrtcbin` or `nicesrc` | Install GStreamer bad-free and libnice GStreamer plugins, then run doctor. |
| No `/dev/video10` | Install/load the matching v4l2loopback kernel module and check Secure Boot/module signing. |
| Installer reports camera setup pending after a kernel update | Reboot into the exact installed kernel printed by the installer. Its camera module is prepared; the boot service creates the device. Exit code 10 means reboot/enrollment remains pending. |
| V4L2 identity rejected | Choose the actual loopback device labeled Kagami, not a physical camera. |
| OBS cannot see camera | Start a producer first when using exclusive caps; refresh OBS's device list and check sandbox device access if OBS is packaged in Flatpak. |
| Permission denied writing camera | Configure normal user device access through Fedora's ACL/group policy. Do not run the UI as root. |
| Pairing expired or used | Restart the host for a fresh five-minute URL, or reconnect with the already authorized browser cookie. |
| Phone lock closes/pauses capture | The host should switch to its no-signal slate. Unlock and start again; browser background capture is not guaranteed. |
