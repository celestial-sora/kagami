# Current tests

Run `python3 -m unittest discover -s tests -v` for headless contracts. Distribution Python with GTK4/GStreamer can run `KAGAMI_TEST_GST=1 G_DEBUG=fatal-criticals python3 -m unittest discover -s tests -v`; this adds actual synthetic frame transforms and H264/RTP decode tests. `xvfb-run -a python3 tools/check_receiver_desktop.py` covers the real GTK window, mode controls, AirPlay without ADB selection and Stop/close.

CI checks contracts, shell/Desktop Entry packaging, pinned MiracleCast/UxPlay builds, real Avahi AirPlay advertisement/teardown, synthetic media and GTK. It no longer builds/tests the removed URL/QR browser service or Rust pairing shell.

`python3 tools/check_airplay_backend.py /path/to/uxplay` is an opt-in backend smoke check requiring active Avahi, avahi-browse and UxPlay 1.73+. It briefly advertises a unique QA name on free test ports and verifies owned-process exit/removal. It never captures an Apple device. See [physical acceptance](receiver-testing.md) and [validation](validation.md).
