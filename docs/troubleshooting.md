# Connection troubleshooting

AirPlay: run `kagami airplay-doctor`, confirm same local network and active Avahi, select AirPlay and Start before opening Screen Mirroring on the sender. Check LAN client isolation and interface-scoped discovery/TCP/UDP firewall rules. Protected surfaces can be black; no physical Apple compatibility has been confirmed.

Smart View: run `kagami smartview-doctor --interface YOUR_INTERFACE`. The selected Linux driver must advertise P2P-client/P2P-GO under supported interface modes. Windows Miracast history does not prove the current Linux driver exposes them. Confirm selected-adapter disconnection in Kagami and complete polkit authentication. See [Smart View](smartview-ubuntu.md).

ADB: unlock/authorize Android and select the matching USB/Wi-Fi device. Require scrcpy 3.0+ with documented V4L2 flags. Wireless debugging Pair and Connect ports may differ. See [ADB setup](receiver-setup.md).

Missing camera: inspect `journalctl -u kagami-receiver-camera.service`, matching kernel headers, DKMS build and pending Secure Boot enrollment. Keep Secure Boot enabled; complete requested MOK enrollment/reboot. Never run the GUI as root or write into a physical camera.

The URL/QR/browser connection workflow has been removed. On disconnect output becomes black; Stop and restart the receiver, then reconnect on the sender. Rotate the sender with reception stopped and adjust crop afterwards.
