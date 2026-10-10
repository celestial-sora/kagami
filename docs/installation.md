# One-command Ubuntu installation

Run in a terminal as your ordinary desktop user on Ubuntu 24.04 or 26.04:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

This installs **Kagami V2**, replacing the normal Kagami application-menu/CLI entry point with the native screen receiver. Samsung Smart View is the default when the selected driver advertises P2P. Otherwise a new installation defaults to AirPlay. Previous V1 app versions, HTTPS config/CA and receiver presets are preserved. The browser URL/QR client, HTTPS/WebRTC pairing service and V1 shell/installer have been removed. Connections use the sender’s Smart View or Screen Mirroring discovery list.

The command requests your sudo password, installs GTK4/Python/GStreamer, Avahi discovery, Wi-Fi Direct tools, matching running-kernel headers and the DKMS virtual camera driver. It downloads Kagami and builds [MiracleCast](https://github.com/albfan/miraclecast) at pinned commit `0b7f1f1f6586dc65ff480f3cda5c2170a70aa020` as your ordinary user. It also builds UxPlay v1.73.2 at `4764e4619e8924f43601d778277fc9f0bf280597`, installing `/usr/local/bin/kagami-uxplay` plus license/version files. Only fixed binaries, D-Bus policy, network helpers and camera service are installed as root. MiracleCast's license is installed with its version record. No Rust build or phone app is required for Smart View.

Internet is needed for installation/updates. Installation leaves Wi-Fi connected; it does not start the receiver, alter global networking, grant passwordless sudo, or open generic firewall ports. During streaming the selected adapter is handed to MiracleCast only after you confirm in Kagami. Custom firewalls may need interface-scoped Miracast rules after the actual P2P interface is known.

## AirPlay

Choose **AirPlay**, click **Check AirPlay**, then **Start**. On an iPhone/iPad/Mac on the same local network, choose **Screen Mirroring → Kagami**. Crop the preview and select Kagami Virtual Camera in OBS. It needs Avahi/mDNS, not Wi-Fi Direct. The installer enables Avahi; user-defined firewalls may need LAN-scoped UDP 5353 and TCP/UDP 35000–35002. See [AirPlay setup](airplay-ubuntu.md). Native Galaxy Smart View remains the separate Miracast mode; no Android AirPlay sender has been validated. Physical Apple interoperability is pending.

## After installation

1. Open **Kagami** from the application menu. The installer selects a Wi-Fi adapter advertising P2P client/GO when one is present; the interface can be changed in the app.
2. Click **Check Smart View**. Confirm the selected adapter may disconnect, then **Start**. Polkit may request authentication for its fixed network helper.
3. On Galaxy choose **Smart View → Kagami**, approve the phone prompt, and open Samsung Camera or the app to mirror.
4. Drag/apply a crop and select **Kagami Virtual Camera** in OBS. The default output is `/dev/video10`; `/dev/video11` is internal screen input. Occupied camera numbers are skipped on first installation, while identified Kagami nodes are reused.
5. Click **Stop** to end reception and restore the adapter's prior network management.

**Real Galaxy discovery, P2P negotiation, network restoration and OBS streaming remain unverified.** Software tests and a successful installation do not prove phone interoperability. See [current Smart View blockers](smartview-ubuntu.md) and [validation](validation.md).

The authoring host's `rtw88_8821ce` driver advertises no P2P-client/P2P-GO. Installation succeeds with AirPlay; that adapter cannot pass Kagami's Smart View preflight. A compatible adapter/driver is required; a separate adapter also allows the primary adapter to keep providing Internet. Do not choose a dongle only by a Wi-Fi generation/marketing label: verify its actual chipset, hardware revision and Linux P2P modes.

USB/ADB fallback remains available in the app but requires a separate authorized ADB/scrcpy 3.0+ installation. It is not needed by this Smart View installer.

## Secure Boot and pending prerequisites

Matching headers for the running kernel are required. DKMS builds the driver and the installer verifies module `vermagic`. Future kernel updates use Ubuntu's normal DKMS package hooks. A custom kernel without matching repository headers or incompatible driver API causes a visible failure; the installer does not change boot defaults or remove kernels.

With Secure Boot enabled, Ubuntu/DKMS signing may require a MOK enrollment password. The installer requests enrollment using the terminal if the signing certificate is not already enrolled. Reboot and choose **Enroll MOK**, confirming with the password you set. The enabled camera service will create the named nodes after reboot; no additional manual helper commands are needed. Secure Boot is never disabled.

Exit status **0** after a full installation means software/camera prerequisite checks passed (an unchanged-commit shortcut only confirms the active app version); it does not mean a Galaxy was tested. **10** means the application was installed but camera MOK enrollment/reboot is pending. Missing P2P is a Smart View availability warning and does not change a successful AirPlay installation to a nonzero exit. **2** means setup or required software checks failed. Package/build commands can also propagate their own failure status. Read the preceding report for the specific missing prerequisite.

## Updates and paths

Run the same curl command to update. The application is versioned by Git SHA/architecture and activated after software checks. Installation settings and explicitly saved crop presets are preserved. The installer resolves the requested ref before downloading and compares the full commit with the active version. An unchanged commit exits without downloading, package installation or builds. During app updates, MiracleCast/UxPlay are reused when their build recipe, Ubuntu version, architecture and binary checks match; otherwise they are rebuilt as your ordinary user. Numbered steps show Check, Download, Install, Build and Verify, with backend configure/compile/stage messages.

| Item | Default path |
|---|---|
| Version switch helper | `~/.local/share/kagami/manage_versions.py` |
| App versions / active version | `~/.local/share/kagami/versions/v2-…` / `current` |
| CLI / desktop launcher | `~/.local/bin/kagami` / `~/.local/share/applications/io.kagami.Host.desktop` |
| Installation settings | `~/.config/kagami/receiver-install.json` |
| Crop presets | `~/.config/kagami/receiver-presets.json` |
| Fixed root helpers | `/usr/local/libexec/kagami-{camera-setup,receiver-camera-setup,smartview-helper,smartview-session}` |
| Camera boot service | `/etc/systemd/system/kagami-receiver-camera.service` |
| Camera ACL rule | `/etc/udev/rules.d/70-kagami-camera.rules` |
| MiracleCast binaries / D-Bus policy | `/usr/local/bin/miracle-{wifid,sinkctl,dhcp}` / `/etc/dbus-1/system.d/org.freedesktop.miracle.conf` |
| MiracleCast license / pinned version / build stamp | `/usr/local/share/doc/kagami-miraclecast/` |
| UxPlay binary / licenses / build stamp | `/usr/local/bin/kagami-uxplay` / `/usr/local/share/doc/kagami-uxplay/` |

`XDG_DATA_HOME` and `XDG_CONFIG_HOME` are honored. The CLI's full path works even when `~/.local/bin` is not in PATH. Saved installation settings initialize the launcher; per-launch flags override them. Stop an already running Kagami app before opening the newly installed version: an update does not kill a running screen receiver.

Inspect the plan without changes:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash -s -- --dry-run
```

Select an adapter explicitly during install (replace `wlan2` with an existing interface):

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | KAGAMI_INTERFACE=wlan2 bash
```

`KAGAMI_REF` on the `bash` side selects a branch, tag or commit. See [source setup](smartview-ubuntu.md) for manual/developer steps.

## Rollback and repair

Stop Kagami before switching versions. Updates preserve app directories and atomically switch `current`, retaining the prior directory through `previous`. To inspect or switch:

```bash
~/.local/bin/kagami versions
~/.local/bin/kagami rollback
```

Rollback swaps current/previous, so running it again restores the newer app. It keeps installation settings and crop presets. It switches the application only: shared Ubuntu packages, DKMS driver, system helpers and pinned backends are not downgraded. An archival V1 directory is retained but cannot be activated through this V2 rollback command because the URL/QR runtime has been removed. Backend changes may require matching prerequisites for older app versions.

The curl installer also accepts `--list-versions` and `--rollback` without app/backend downloads or root installation. To repeat prerequisite checks after a kernel update, MOK enrollment or damaged system installation, use:

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash -s -- --repair
```

Repair repeats setup even at the same app commit; matching usable backend builds are still reused.

## Stable releases

The development default remains `main`. `KAGAMI_REF` already accepts release tags and full commit IDs; annotated tags are resolved to their commit before comparison/download. Once tested GitHub Releases are published, the default channel can move to a release-pinned installer with checksummed artifacts. No stable release or prebuilt artifact is claimed by the current installer. Use an actually published tag on the bash side, for example `KAGAMI_REF=<published-tag> bash`, instead of inventing a version name.

UxPlay v1.73.2 is built with a narrow compatibility fix adding its missing `<stdio.h>` declaration for GCC 14/15. Kagami retains the pinned upstream commit and normal compiler error checks. This fixes the actual Ubuntu 26.04/GCC 15 build failure; no compiler errors are suppressed.
