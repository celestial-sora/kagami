# One-command Ubuntu installation

Run in a terminal as your ordinary desktop user on Ubuntu 24.04 or 26.04:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

This installs **Kagami V2**, replacing the normal Kagami application-menu/CLI entry point with the native screen receiver. Samsung Smart View is the default, experimental transport. Previous V1 app versions, HTTPS config/CA and receiver presets are preserved. The retained Fedora browser bridge has a separate [V1 installer](installation-v1.md).

The command requests your sudo password, installs GTK4/Python/GStreamer, Wi-Fi Direct tools, matching running-kernel headers and the DKMS virtual camera driver. It downloads Kagami and builds [MiracleCast](https://github.com/albfan/miraclecast) at pinned commit `0b7f1f1f6586dc65ff480f3cda5c2170a70aa020` as your ordinary user. Only fixed binaries, D-Bus policy, network helpers and camera service are installed as root. MiracleCast's license is installed with its version record. No Rust build or phone app is required for Smart View.

Internet is needed for installation/updates. Installation leaves Wi-Fi connected; it does not start the receiver, alter global networking, grant passwordless sudo, or open generic firewall ports. During streaming the selected adapter is handed to MiracleCast only after you confirm in Kagami. Custom firewalls may need interface-scoped Miracast rules after the actual P2P interface is known.

## After installation

1. Open **Kagami** from the application menu. The installer selects a Wi-Fi adapter advertising P2P client/GO when one is present; the interface can be changed in the app.
2. Click **Check Smart View**. Confirm the selected adapter may disconnect, then **Start**. Polkit may request authentication for its fixed network helper.
3. On Galaxy choose **Smart View → Kagami**, approve the phone prompt, and open Samsung Camera or the app to mirror.
4. Drag/apply a crop and select **Kagami Virtual Camera** in OBS. The default output is `/dev/video10`; `/dev/video11` is internal screen input. Occupied camera numbers are skipped on first installation, while identified Kagami nodes are reused.
5. Click **Stop** to end reception and restore the adapter's prior network management.

**Real Galaxy discovery, P2P negotiation, network restoration and OBS streaming remain unverified.** Software tests and a successful installation do not prove phone interoperability. See [current Smart View blockers](smartview-ubuntu.md) and [validation](validation.md).

The authoring host's `rtw88_8821ce` driver advertises no P2P-client/P2P-GO. The software can be installed, but that adapter cannot pass Kagami's Smart View preflight. A compatible adapter/driver is required; a separate adapter also allows the primary adapter to keep providing Internet. Do not choose a dongle only by a Wi-Fi generation/marketing label: verify its actual chipset, hardware revision and Linux P2P modes.

USB/ADB fallback remains available in the app but requires a separate authorized ADB/scrcpy 3.0+ installation. It is not needed by this Smart View installer.

## Secure Boot and pending prerequisites

Matching headers for the running kernel are required. DKMS builds the driver and the installer verifies module `vermagic`. Future kernel updates use Ubuntu's normal DKMS package hooks. A custom kernel without matching repository headers or incompatible driver API causes a visible failure; the installer does not change boot defaults or remove kernels.

With Secure Boot enabled, Ubuntu/DKMS signing may require a MOK enrollment password. The installer requests enrollment using the terminal if the signing certificate is not already enrolled. Reboot and choose **Enroll MOK**, confirming with the password you set. The enabled camera service will create the named nodes after reboot; no additional manual helper commands are needed. Secure Boot is never disabled.

Exit status **0** means software/camera prerequisite checks passed; it does not mean a Galaxy was tested. **10** means the application was installed but MOK enrollment/reboot or P2P hardware is pending. **2** means setup or required software checks failed. Package/build commands can also propagate their own failure status. Read the preceding report for the specific missing prerequisite.

## Updates and paths

Run the same curl command to update. The application is versioned by Git SHA/architecture and activated after software checks. Installation settings and explicitly saved crop presets are preserved. Re-running currently rebuilds pinned MiracleCast in a fresh staging directory.

| Item | Default path |
|---|---|
| App versions / active version | `~/.local/share/kagami/versions/v2-…` / `current` |
| CLI / desktop launcher | `~/.local/bin/kagami` / `~/.local/share/applications/io.kagami.Host.desktop` |
| Installation settings | `~/.config/kagami/receiver-install.json` |
| Crop presets | `~/.config/kagami/receiver-presets.json` |
| Fixed root helpers | `/usr/local/libexec/kagami-{camera-setup,receiver-camera-setup,smartview-helper,smartview-session}` |
| Camera boot service | `/etc/systemd/system/kagami-receiver-camera.service` |
| Camera ACL rule | `/etc/udev/rules.d/70-kagami-camera.rules` |
| MiracleCast binaries / D-Bus policy | `/usr/local/bin/miracle-{wifid,sinkctl,dhcp}` / `/etc/dbus-1/system.d/org.freedesktop.miracle.conf` |
| MiracleCast license / pinned version | `/usr/local/share/doc/kagami-miraclecast/` |

`XDG_DATA_HOME` and `XDG_CONFIG_HOME` are honored. The CLI's full path works even when `~/.local/bin` is not in PATH. Saved installation settings initialize the launcher; per-launch flags override them. Stop an already running V1/V2 app before opening the newly installed version: an update does not kill a running screen receiver.

Inspect the plan without changes:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash -s -- --dry-run
```

Select an adapter explicitly during install (replace `wlan2` with an existing interface):

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | KAGAMI_INTERFACE=wlan2 bash
```

`KAGAMI_REF` on the `bash` side selects a branch, tag or commit. See [source setup](smartview-ubuntu.md) for manual/developer steps.
