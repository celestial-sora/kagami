# Receiver migration audit

Baseline main e5cc265 included the Ubuntu receiver/curl installer plus retained V1 browser, HTTPS/WebRTC service and QR Rust shell. The maintainer explicitly requested AirPlay and removal of URL/QR pairing. The current change adds an owned UxPlay transport with local H264/RTP decoding and removes the old client/service/shell, V1 installer and obsolete dependency/test paths. The shared V4L2 identity guard moved into the active receiver.

The current installer builds pinned MiracleCast/UxPlay as the ordinary user and installs fixed root-owned helpers plus the current user launcher. Prior app versions/settings/presets are retained; no old connection service is started. CI now tests active receiver/contracts/packaging and backend builds/discovery rather than the removed product.

The authoring host is Ubuntu 26.04, RTL8821CE [10ec:c821], driver rtw88_8821ce, lacking advertised P2P modes. Windows Miracast history narrows the present blocker to Linux-driver capabilities; no replacement-driver or host network changes were performed. AirPlay uses same-LAN Avahi and does not need P2P.

The authorized Ubuntu 26.04 installer now passes with AirPlay despite missing P2P, including actual DKMS/module/camera setup and black waiting frames through video10. Physical Apple/Galaxy media, OBS, network restoration, enabled Secure Boot and post-reboot acceptance remain open. See [validation](validation.md).
