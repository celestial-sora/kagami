# AirPlay on Ubuntu

Kagami's experimental AirPlay adapter uses [UxPlay](https://github.com/FDH2/UxPlay) 1.73+ as a separate, unprivileged protocol/discovery process. The curl installer builds inspected UxPlay v1.73.2 at `4764e4619e8924f43601d778277fc9f0bf280597` and installs it as `/usr/local/bin/kagami-uxplay`, preserving any independent `uxplay` installation. License, llhttp license and version record are under `/usr/local/share/doc/kagami-uxplay/`.

## Use

Run the [one-command installer](installation.md), then open Kagami. Choose **AirPlay**, click **Check AirPlay**, then **Start AirPlay** in the fixed top controls. On iPhone/iPad/Mac open **Screen Mirroring → Kagami** while connected to the same local network. Apply a crop and select **Kagami Virtual Camera** in OBS. Click Stop in Kagami to stop its receiver and decoding. Merely opening the app does not advertise Kagami: it appears in Screen Mirroring only while the receiver is started. The Start/Stop buttons and status remain visible above the scrollable preview/settings, including on smaller windows.

AirPlay needs ordinary LAN access and Avahi/mDNS discovery; it does not require P2P-client/P2P-GO or disconnect the Wi-Fi adapter. Native Galaxy Smart View is a Miracast sender. A Samsung device would require a separate AirPlay sender implementation; no Android sender app has been selected or validated here.

## Media and lifecycle

Kagami passes the documented `-vrtp` forwarding option to UxPlay. Decrypted H264 is packetized as RTP payload 96 and forwarded only to `127.0.0.1` on a dynamically chosen local UDP port. Kagami's own GStreamer decoder accepts that loopback stream, decodes it, and normalizes it into I420 1280×720 with aspect-preserving side/top borders. The identified Screen Input loopback feeds the same crop/rotation/mirror/FPS/output pipeline as Smart View and ADB.

A fixed input canvas keeps V4L2 dimensions stable when the sender changes orientation. Crop is expressed in that canvas; portrait borders can be cropped. Stop/restart after changing orientation and adjust framing. This does not implement automatic orientation/preset tracking.

UxPlay receives `-rc /dev/null` so personal startup files cannot activate recordings or change Kagami's bridge. Audio, HLS streaming and H265 are not enabled. Screen media is not saved. Logs and frame queues are bounded. Missing frames for four seconds after a stream has started terminate the owned listener/decoder and leave the shared output black until Stop/reconnect. Before first connection, the listener waits without the ADB timeout. Wireless phone identity/preset saving is disabled.

## Diagnostics and network

```bash
bash tools/run-receiver.sh airplay-doctor
bash tools/run-receiver.sh airplay
```

Installed CLI: `~/.local/bin/kagami airplay-doctor` or `~/.local/bin/kagami airplay`. Headless `--airplay-port 35000` chooses the base of three TCP and three UDP ports (35000–35002 by default). Discovery uses UDP 5353. The dynamic RTP bridge is local only and needs no LAN firewall opening.

On a custom firewall, permit UDP 5353 for local discovery and TCP/UDP 35000–35002 from the sender's trusted LAN on the relevant interface. Keep client isolation off for the two devices; cross-VLAN discovery/forwarding is not configured by Kagami. Installation starts Avahi and does not modify global Wi-Fi management or generic firewall rules.

## Verification limits

Contracts cover capabilities, dependency failures, loopback bridge configuration, no recording, stale-stream handling, partial-start cleanup and real child teardown. A real synthetic portrait H264/RTP stream proves decoding, changing frames, fixed dimensions and side borders. CI additionally builds actual UxPlay and checks its real Avahi advertisement/teardown. Those checks do not authenticate an Apple device or exercise real AirPlay negotiation, screen capture, V4L2 kernel nodes or OBS. Physical iPhone/iPad/Mac acceptance remains pending.
