> **Maintainer update:** primary target is now **Ubuntu + Samsung Smart View**, ahead of USB. See [Smart View setup/status](smartview-ubuntu.md). The MiracleCast receiver prototype is integrated but physical Galaxy/P2P acceptance remains open; USB is a fallback. Earlier Fedora/USB rollout references below are historical context.

# V2 physical acceptance checklist

Automated synthetic tests prove framing/lifecycle contracts, not Samsung/OBS compatibility. Do not label the USB MVP hardware-accepted until the checks below pass.

Record Fedora release/kernel, Wayland compositor, phone model, Android/One UI, scrcpy/GStreamer/OBS/Discord versions, USB cable and selected `/dev/videoN` nodes. For wireless/Smart View also record Wi-Fi adapter/driver/P2P support and network topology.

| Area | Procedure | Required evidence |
| --- | --- | --- |
| USB / authorization | Refresh with an unauthorized phone, authorize on phone, refresh again | Correct serial, actionable unauthorized status, no automatic permission grants |
| Samsung Camera | Open Camera before Start | Moving camera image in screen preview, no unexpected protected/black surface |
| TikTok | Test a specific effect separately | Effect visible in preview and V4L2 when app permits; record blocked surfaces honestly |
| Crop | Drag around preview excluding shutter/control area | Processed preview and OBS show only the selected rectangle; internal overlays remain |
| Transform | Test 16:9/4:3/1:1/portrait, every rotation, mirror, fit/fill | No stretched frames; correct order; output dimensions constant |
| Orientation | Stop, rotate phone, restart; load saved presets | Matching captured-size preset only; no unsafe reuse of old pixel crop |
| OBS | Select actual output node as V4L2 capture | Moving image, run 15 minutes, record actual incoming/output FPS and CPU/RAM |
| Second consumer | Close conflicting consumers if needed; use Discord or `ffplay -f v4l2 -i /dev/video10` | Actual live output opens and remains stable; record format/caps |
| Disconnect | Unplug cable while OBS remains open | Black output/slate, actionable disconnect, no scrcpy writer left running; explicit reconnect succeeds |
| Stop / exit | Stop, restart, close window, SIGTERM during capture | No orphan scrcpy child; output device released after Stop |
| Wi-Fi | Explicit wireless pair/connect, stream, disconnect/reconnect | Same framing/output; compare FPS and measured latency separately from USB |
| Latency | Film phone and consumer showing a repeatable changing timer | Empirical glass-to-glass result with method; host timestamp age alone is insufficient |
| Fedora boot/kernel | Reboot into each prepared kernel | Both named nodes exist and normal desktop user can access them |

Optional hardware commands (run only after selecting the actual nodes):

```bash
bash tools/run-receiver.sh doctor --source /dev/video11 --output /dev/video10
v4l2-ctl -d /dev/video10 --all
ffplay -f v4l2 -i /dev/video10
```

Keep screen recordings/screenshots off by default; collect only consented test content. Android dialogs and protected surfaces must not be bypassed. Miracast/Smart View and Google Cast acceptance are separate future investigations, not USB milestones.
