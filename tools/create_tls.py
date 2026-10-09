#!/usr/bin/env python3
"""Create a per-installation CA and an IP SAN server certificate using OpenSSL."""

import argparse
import ipaddress
import os
from pathlib import Path
import shutil
import subprocess
import sys


def create_tls(directory, hosts):
    directory = Path(directory).resolve()
    names = ("ca.key", "ca.pem", "server.key", "server.pem", "server.csr", "server.ext", "ca.srl")
    if any((directory / name).exists() for name in names):
        raise ValueError("TLS files already exist. Use a new directory; do not silently replace a trusted CA.")
    if not shutil.which("openssl"):
        raise ValueError("OpenSSL is required.")
    addresses = []
    for host in hosts:
        address = ipaddress.IPv4Address(host)
        if address.is_unspecified or address.is_multicast or not (address.is_private or address.is_loopback):
            raise ValueError("Certificate hosts must be reachable local IPv4 addresses.")
        addresses.append(str(address))
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    extensions = ("basicConstraints=critical,CA:FALSE\n"
                  "keyUsage=critical,digitalSignature,keyEncipherment\n"
                  "extendedKeyUsage=serverAuth\n"
                  "subjectAltName=" + ",".join(f"IP:{value}" for value in addresses) + "\n")
    (directory / "server.ext").write_text(extensions, encoding="utf-8")

    def run(*args):
        result = subprocess.run(["openssl", *args], cwd=directory, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())

    previous_umask = os.umask(0o077)
    try:
        run("req", "-x509", "-newkey", "rsa:3072", "-sha256", "-nodes", "-days", "365",
            "-subj", "/CN=Kagami Local CA", "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-keyout", "ca.key", "-out", "ca.pem")
        run("req", "-new", "-newkey", "rsa:2048", "-sha256", "-nodes", "-subj", "/CN=Kagami Host",
            "-keyout", "server.key", "-out", "server.csr")
        run("x509", "-req", "-in", "server.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
            "-out", "server.pem", "-days", "90", "-sha256", "-extfile", "server.ext")
        for name in names:
            if (directory / name).exists():
                os.chmod(directory / name, 0o600)
    finally:
        os.umask(previous_umask)
    return directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", action="append", required=True, help="Local IPv4; repeat for Wi-Fi and USB addresses")
    parser.add_argument("--out", type=Path, default=Path(".local/tls"))
    args = parser.parse_args()
    try:
        directory = create_tls(args.out, args.host)
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Created TLS files in {directory}. Transfer only ca.pem to the phone through a trusted local channel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
