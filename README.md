<div align="center">

<img src="assets/kagami-icon.webp" alt="Kagami icon" width="128">

# Kagami · 鏡

### Your phone screen. Your virtual camera.

**Mirror from your phone to Linux, then use it in OBS.**

[![Latest release](https://img.shields.io/github/v/release/celestial-sora/kagami?label=Release&style=flat-square)](https://github.com/celestial-sora/kagami/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/celestial-sora/kagami/ci.yml?branch=main&label=Checks&style=flat-square)](https://github.com/celestial-sora/kagami/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-555?style=flat-square)](LICENSE)

[**Install**](#install) · [**Supported Linux**](#linux-support) · [**How it works**](#how-it-works) · [**Latest release**](https://github.com/celestial-sora/kagami/releases/latest)

<img src="assets/screenshots/kagami-airplay-ipad.png" alt="iPad AirPlay mirroring in the Kagami desktop app" width="760">

<sub>Real iPad AirPlay preview in Kagami. No Kagami mobile app required.</sub>

</div>

## What is Kagami?

Kagami turns a compatible phone or tablet screen into a **V4L2 virtual camera** on Linux. Mirror locally, adjust your framing, and select **Kagami Virtual Camera** in OBS.

- **Local-first.** No account or cloud relay.
- **Wireless mirroring.** AirPlay for Apple devices; experimental Samsung Smart View.
- **Camera-ready.** Crop, rotate and mirror your preview before sending it to OBS.

> **ภาษาไทย:** Kagami รับภาพหน้าจอมือถือผ่านเครือข่ายภายใน แล้วส่งเป็น Virtual Camera บน Linux สำหรับ OBS โดยไม่ต้องติดตั้งแอป Kagami ในมือถือ

## Install

**Linux development installer** (Ubuntu, Debian, Arch, Manjaro, EndeavourOS and Fedora families):

```bash
curl -fsSL https://raw.githubusercontent.com/celestial-sora/kagami/main/install.sh | bash
```

Run as your **normal desktop user**, not with `sudo` in front of the command. The installer requests authentication only for system prerequisites. Running the same command again checks for updates.

> [!NOTE]
> This installs the latest **development** commit, not a pinned stable release. The published stable installer may support fewer distributions. Check [Releases](https://github.com/celestial-sora/kagami/releases/latest) for the latest published assets and release notes.

<details>
<summary><strong>Stable installer · Ubuntu 24.04 / 26.04</strong></summary>

```bash
curl -fsSL https://github.com/celestial-sora/kagami/releases/latest/download/install-kagami.sh | bash
```

Use the stable command only on the platforms supported by the release's own notes. It may not include the newer Arch/Manjaro/Fedora installer changes.

</details>

<details>
<summary><strong>AppImage · x86_64</strong></summary>

Find the AppImage artifact in [successful CI runs](https://github.com/celestial-sora/kagami/actions/workflows/ci.yml) or in a release when one is attached.

The AppImage still needs host camera drivers, camera node permissions and discovery services. Follow the [AppImage setup guide](docs/linux-distributions.md#appimage) before running it.

</details>

## Linux support

| Distribution | Install method | Validation |
| :-- | :-- | :-- |
| **Ubuntu 24.04 / 26.04** | `apt` | Real iPad → Kagami → OBS verified on Ubuntu 26.04 |
| **Debian 12+** · Linux Mint · Pop!_OS | `apt` | Userspace CI; desktop/device testing pending |
| **Arch Linux** · **Manjaro** · **EndeavourOS** | `pacman` | Arch userspace CI; Manjaro/EndeavourOS device testing pending |
| **Fedora Workstation** and compatible derivatives | `dnf` | Userspace CI; desktop/device testing pending |

**Requirements:** systemd desktop, Python 3.10+, GTK 4.8+, GStreamer 1.22+, matching headers for your running kernel, and V4L2 camera support.

Arch-based installs perform a full `pacman -Syu` to avoid partial upgrades. On Manjaro, **reboot into your updated kernel** if needed before rerunning the installer. Unsupported environments include immutable/Atomic desktops and non-systemd hosts.

[**Full distribution compatibility & kernel notes →**](docs/linux-distributions.md)

## How it works

| Your device | Connect with | Status |
| :-- | :-- | :-- |
| iPhone / iPad / Mac | **AirPlay** · Screen Mirroring on the same local network | iPad video verified on Ubuntu |
| Samsung Galaxy | **Smart View** · Wi-Fi Direct (P2P) | Experimental; P2P-capable adapter required |
| Android | **USB or Wi-Fi ADB** · scrcpy 3.0+ | Requires separate authorized ADB/scrcpy setup |

1. Open **Kagami** from your applications menu.
2. Choose a connection mode, then **Check → Start**.
3. Connect your phone and adjust your crop.
4. In OBS, add **Video Capture Device (V4L2)** and select **Kagami Virtual Camera**.

<div align="center">

<img src="assets/screenshots/kagami-airplay-idle.png" alt="Kagami AirPlay idle screen" width="49%">
<img src="assets/screenshots/kagami-airplay-ipad.png" alt="Kagami displaying an iPad AirPlay stream" width="49%">

<sub>AirPlay: ready → connected</sub>

</div>

> [!IMPORTANT]
> Successful installation or CI does **not** prove every phone and Linux distribution works end to end. Real Samsung Smart View, further Apple devices, Secure Boot and distro-specific kernel/camera behavior still need physical testing.

## Help & development

[**Installation guide**](docs/installation.md) · [**Linux / AppImage details**](docs/linux-distributions.md) · [**Tested behavior**](docs/validation.md) · [**Issues**](https://github.com/celestial-sora/kagami/issues)

<details>
<summary><strong>Technical notes</strong></summary>

Kagami uses GTK4, GStreamer, a V4L2 loopback camera and local discovery. Its Linux receiver integrates UxPlay for AirPlay and MiracleCast for experimental Smart View. The app preserves settings, crop presets and previous installed versions for rollback. AirPlay audio plays through desktop output for capture via OBS Desktop Audio.

The development installer builds required backend components locally. Kernel headers must match `uname -r`; Secure Boot may require DKMS MOK enrollment and a reboot. Hardware and distribution validation details are maintained in [docs/validation.md](docs/validation.md).

</details>

---

<div align="center">

Made by [celestial-sora](https://github.com/celestial-sora) · [MIT License](LICENSE)

<sub>Third-party components retain their respective upstream licenses.</sub>

</div>
