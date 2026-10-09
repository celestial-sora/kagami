# USB uses local IP networking

1. Connect the Android phone to Linux with a data cable and enable USB tethering in Android settings.
2. Use NetworkManager or `ip -4 address` to identify the computer's new USB network interface and IPv4 address.
3. Update `config.json` to that host address; do not reuse a Wi-Fi URL unless the phone can actually reach it through this link.
4. Ensure the server certificate SAN contains the USB host address, then start the host and pair.
5. Test with Wi-Fi and mobile Internet unavailable to verify that the selected media path uses the USB link. Record the actual route/candidate behavior rather than treating a successful URL load as proof of media connectivity.

This is not UVC device emulation or raw USB transport. No ADB/debugging mode is required. USB tethering creates the IP connection used by the same HTTPS/WebRTC protocol. Phone/OS routing behavior and browser ICE candidates still require target-device testing.
