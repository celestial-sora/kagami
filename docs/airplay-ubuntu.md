# AirPlay on Ubuntu

Kagami's experimental AirPlay adapter uses [UxPlay](https://github.com/FDH2/UxPlay) as a separate, unprivileged protocol/discovery process. The curl installer builds inspected UxPlay v1.73.2 at `4764e4619e8924f43601d778277fc9f0bf280597` with Kagami's timestamp and lifecycle fixes and installs it as `/usr/local/bin/kagami-uxplay`, preserving any independent `uxplay` installation. The receiver requires the `KAGAMI_AIRPLAY_EVENTS_V1` capability in backend help; an unpatched standalone UxPlay is insufficient. License, llhttp license and version record are under `/usr/local/share/doc/kagami-uxplay/`.

## Use

Run the [one-command installer](installation.md), then open Kagami. Choose **AirPlay**, click **Check AirPlay**, then **Start AirPlay** in the fixed top controls. On iPhone/iPad/Mac open **Screen Mirroring → Kagami** while connected to the same local network. Apply a crop and select **Kagami Virtual Camera** in OBS. Click Stop in Kagami to stop its receiver and decoding. Merely opening the app does not advertise Kagami: it appears in Screen Mirroring only while the receiver is started. The Start/Stop buttons and status remain visible above the scrollable preview/settings, including on smaller windows.

AirPlay needs ordinary LAN access and Avahi/mDNS discovery; it does not require P2P-client/P2P-GO or disconnect the Wi-Fi adapter. Native Galaxy Smart View is a Miracast sender. A Samsung device would require a separate AirPlay sender implementation; no Android sender app has been selected or validated here.

## Camera output size

For 1920×1080 output, stop Kagami and deactivate its camera source in OBS/Discord (or close the consumer), select **1920×1080**, then start Kagami and reactivate the camera source. A consumer holding the old capture buffers pins the previous dimensions even after Kagami stops. The receiver checks available dimensions before starting AirPlay and explains how to release the camera if the requested size is blocked; Start remains retryable.

The selected size controls the Virtual Camera output. AirPlay's input canvas remains 1280×720, so selecting 1080p scales that canvas. The maintainer confirms 1080p works after releasing the OBS camera.

## Media and lifecycle

Kagami passes the documented `-vrtp` forwarding option to UxPlay. Decrypted H264 is packetized as RTP payload 96 and forwarded only to `127.0.0.1` on a dynamically chosen local UDP port. Kagami's own GStreamer decoder accepts that loopback stream, decodes it, and normalizes it into I420 1280×720 with aspect-preserving side/top borders. The identified Screen Input loopback feeds the same crop/rotation/mirror/FPS/output pipeline as Smart View and ADB.

The pinned backend gets two compatibility fixes: the missing stdio.h declaration on GCC 14+, and presentation timestamps during RTP forwarding. Unpatched v1.73.2 sends a constant RTP timestamp, causing decoded frames to be discarded. The local bridge depacketizes directly; its bounded leaky queue holds decoded frames so it cannot discard H264 references before decoding. The camera writer uses one fixed-format appsrc at the selected FPS for both video and black slate, preventing a format change while OBS holds camera buffers.

A fixed input canvas keeps V4L2 dimensions stable when the sender changes orientation. Crop is expressed in that canvas; portrait borders can be cropped. Stop/restart after changing orientation and adjust framing. This does not implement automatic orientation/preset tracking.

UxPlay receives `-rc /dev/null` so personal startup files cannot activate recordings or change Kagami's bridge. Audio, HLS streaming and H265 are not enabled. Screen media is not saved. Logs and frame queues are bounded. A static screen may stop producing changed video: Kagami retains the latest frame and keeps the camera writer at the chosen FPS, without an idle media timeout. Explicit video teardown, video TCP EOF, all client control connections closing, connection reset or UxPlay's existing client-feedback watchdog emit a fixed, immediately flushed disconnect event. The receiver then stops its owned listener/decoder and leaves the output black until Stop/reconnect. Discovery probes closing before any mirrored video do not trigger that event. Before first connection, the listener waits without the ADB timeout. Wireless phone identity/preset saving is disabled.

## Diagnostics and network

```bash
bash tools/run-receiver.sh airplay-doctor
bash tools/run-receiver.sh airplay
```

Installed CLI: `~/.local/bin/kagami airplay-doctor` or `~/.local/bin/kagami airplay`. Headless `--airplay-port 35000` chooses the base of three TCP and three UDP ports (35000–35002 by default). Discovery uses UDP 5353. The dynamic RTP bridge is local only and needs no LAN firewall opening.

On a custom firewall, permit UDP 5353 for local discovery and TCP/UDP 35000–35002 from the sender's trusted LAN on the relevant interface. Keep client isolation off for the two devices; cross-VLAN discovery/forwarding is not configured by Kagami. Installation starts Avahi and does not modify global Wi-Fi management or generic firewall rules.

## Verification limits

Contracts cover capabilities, dependency failures, loopback bridge configuration, no recording, idle frame retention, protocol disconnect, partial-start cleanup and real child teardown. Synthetic portrait H264/RTP proves decoding and fixed dimensions; compiled checks against the actual UxPlay sources prove advancing RTP timestamps and ten minutes of simulated feedback ticks without changed video, followed by real callback-driven disconnects. A synthetic camera consumer verifies repeated identical frames and black output after disconnect. On Ubuntu 26.04 the maintainer confirmed real iPad discovery and visible mirrored video in both Kagami and OBS, and reports gaming for over ten minutes. Actual long static-screen acceptance of the idle correction, other Apple devices and reconnect/orientation acceptance remain pending; see [validation](validation.md).
