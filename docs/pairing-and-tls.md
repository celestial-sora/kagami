# Pairing and trusted HTTPS

The phone browser's camera API requires a secure context. Typing `http://<computer-IP>` or ignoring an untrusted self-signed certificate is not the supported setup.

1. Choose the computer's Wi-Fi or USB IPv4 address and put it in `config.json`.
2. Run `python3 tools/create_tls.py --host <address>`. Repeat `--host` for multiple addresses that should be included in the certificate's SAN.
3. Transfer **only `ca.pem`** to Android through a trusted local channel such as a cable. Never transfer `ca.key` or `server.key`.
4. Import the CA using the device's certificate settings and verify that the target browser accepts the host's certificate. OEM settings and browser trust behavior vary; record the Android/browser version used. This workflow still needs physical-device acceptance.
5. Start the host and scan its QR/URL. The one-time 256-bit pairing secret is carried in the URL fragment, removed from browser history, and exchanged over HTTPS for an HttpOnly, Secure, SameSite=Strict cookie.
6. Click **Start camera** to grant camera permission and start streaming.

The QR alone cannot establish browser certificate trust. Both the CA and a matching IP SAN certificate are required. The app never uses `CERT_NONE`, ignores SSL failures, or disables browser security flags in production.

Pairing expires after 5 minutes and may be exchanged once. The authorized session lasts 8 hours and supports reconnect. Restarting/stopping the host revokes its in-memory credentials. Restart for a fresh QR if pairing expired or the browser lost its cookie.

CA/server keys remain local in a private directory. The utility refuses to overwrite an existing CA. The prototype server certificate expires after 90 days and the CA after one year; automatic renewal is not implemented. Address changes require a matching certificate, and certificate renewal/trust UX is a later engineering task.

Reference: [MDN getUserMedia security requirements](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia#privacy_and_security).
