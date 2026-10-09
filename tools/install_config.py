#!/usr/bin/env python3
"""Unprivileged installer configuration; keep existing settings and CA identity."""

import argparse
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import ssl
import sys

from create_tls import create_tls

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/host"))
from kagami_host.config import load_config


def local_links(interfaces):
    links = []
    excluded = ("lo", "docker", "veth", "virbr", "br-", "podman", "wg", "tailscale", "tun")
    for interface in interfaces:
        name = interface.get("ifname", "")
        if not name or name.startswith(excluded):
            continue
        for address in interface.get("addr_info", []):
            if address.get("family") != "inet" or address.get("scope") != "global":
                continue
            item = ipaddress.IPv4Interface(f"{address['local']}/{address['prefixlen']}")
            if item.ip.is_private and not item.ip.is_loopback and item.network.is_private:
                links.append({"host": str(item.ip), "subnet": str(item.network), "interface": name})
    return links


def choose_link(interfaces, routes, preferred=None):
    links = local_links(interfaces)
    if preferred:
        for link in links:
            if link["host"] == preferred:
                return link
        raise ValueError(f"Host {preferred} is not on an active local interface. Connect Wi-Fi/USB first.")
    for route in sorted(routes, key=lambda value: value.get("metric", 0)):
        for link in links:
            if link["interface"] == route.get("dev"):
                return link
    if links:
        return links[0]
    raise ValueError("No reachable private IPv4 interface. Connect Wi-Fi or enable USB tethering, then rerun the installer.")


def prepare(directory, device, interfaces, routes, preferred=None):
    directory = Path(directory).resolve()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    path = directory / "config.json"
    if path.exists():
        config = load_config(path)
        link = choose_link(interfaces, routes, preferred or config.host)
        if link["host"] != config.host or config.device != device:
            raise ValueError("Existing configuration uses a different host/device; it was preserved. See docs/installation.md.")
        for file in (config.certificate, config.private_key):
            if not file.is_file():
                raise ValueError(f"Existing TLS file is missing: {file}. Configuration was preserved.")
    else:
        link = choose_link(interfaces, routes, preferred)
        hosts = [entry["host"] for entry in local_links(interfaces)]
        create_tls(directory / "tls", hosts)
        values = {"host": link["host"], "port": 8443, "device": device,
                  "certificate": "tls/server.pem", "private_key": "tls/server.key",
                  "width": 1280, "height": 720, "fps": 30,
                  "udp_port_min": 50000, "udp_port_max": 50100}
        # Exclusive creation prevents replacing a user configuration on a race.
        with path.open("x", encoding="utf-8") as output:
            json.dump(values, output, indent=2)
            output.write("\n")
        os.chmod(path, 0o600)
        config = load_config(path)
    # Check name and expiry with OpenSSL without weakening TLS validation.
    ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(config.certificate, config.private_key)
    ca = config.certificate.parent / "ca.pem"
    subprocess.run(["openssl", "verify", "-CAfile", str(ca),
                    "-verify_ip", config.host, str(config.certificate)], check=True, capture_output=True)
    return {**link, "port": config.port, "udp_min": config.udp_port_min,
            "udp_max": config.udp_port_max, "config": str(path),
            "ca": str(ca)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--host")
    args = parser.parse_args()
    try:
        interfaces = json.loads(subprocess.check_output(["ip", "-j", "-4", "address", "show", "up", "scope", "global"], text=True))
        routes = json.loads(subprocess.check_output(["ip", "-j", "-4", "route", "show", "default"], text=True))
        print(json.dumps(prepare(args.directory, args.device, interfaces, routes, args.host)))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Kagami configuration needs attention: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
