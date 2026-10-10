<div align="center">

<img src="assets/kagami-icon.webp" width="144" height="144" alt="Kagami app icon">

# Kagami · 鏡

**Your phone screen, now a virtual camera for Linux.**

**Phone / Tablet → Kagami → OBS / Discord**

Ubuntu 24.04 / 26.04 · Native GTK4 · Local-first · No account · MIT

</div>

Kagami receives a phone's **mirrored screen**, lets you crop and adjust the picture, and publishes it as **Kagami Virtual Camera** on Ubuntu. No separate Kagami phone app, cloud relay, browser pairing page, or QR code is required.

## Install / ติดตั้ง

Open a terminal on **Ubuntu 24.04 or 26.04** and run this as your normal desktop user:

~~~bash
curl -fsSL https://github.com/celestial-sora/kagami/releases/latest/download/install-kagami.sh | bash
~~~

The latest stable installer selects its published release tag by default. The installer sets up the desktop app, receiver dependencies, and virtual camera. It may request your **sudo password**. If Secure Boot is enabled, camera-driver enrollment may also require a reboot. [Read the installation guide](docs/installation.md) or [inspect the script](install.sh) before running it.

**Choose a language below. Each guide expands when clicked.**  
**เลือกภาษาด้านล่าง แล้วกดเพื่อเปิดหรือปิดคู่มือได้เลย**

<details>
<summary><strong>🇬🇧 English · Open user guide</strong></summary>

### Get started

1. Launch **Kagami** from your Ubuntu application menu.
2. Pick a connection mode and click its **Check** button.
3. Click **Start** in Kagami. The receiver now becomes discoverable for the selected wireless mode.
4. Connect your phone using the instructions in the table below.
5. Drag and apply a **crop**, then adjust rotation, mirror, fit/fill, or output resolution as needed.
6. In OBS, add a **Video Capture Device (V4L2)** source and choose **Kagami Virtual Camera**. Click **Stop** in Kagami when finished.

### Choose a connection

| Mode | On your device | Before you start |
| :--- | :--- | :--- |
| **AirPlay** | iPhone / iPad / Mac → **Screen Mirroring** → **Kagami** | Both devices on the same local network; Avahi/mDNS available |
| **Samsung Smart View** | Galaxy → **Smart View** → **Kagami** | Compatible Linux Wi-Fi Direct (P2P client/GO) adapter/driver; experimental |
| **USB Mirror** | Plug in an Android phone and approve **USB debugging** | Data cable, authorized ADB, and scrcpy 3.0+ |
| **Wi-Fi ADB Mirror** | Android **Wireless debugging** → pair and connect in Kagami | Trusted private network, authorized ADB, and scrcpy 3.0+ |

**Which mode should I try first?** Use **AirPlay** for an iPhone/iPad, or **Smart View** for a Galaxy with supported Linux P2P. If the latter is unavailable, USB/ADB is a fallback. ADB and scrcpy are separate prerequisites and are not installed by the main receiver installer.

### What works today?

- **AirPlay:** Real iPad screen mirroring has shown video in both Kagami and OBS on Ubuntu 26.04. This does **not** verify every iPhone, Mac, reconnect scenario, or long static-screen session.
- **Smart View:** The Miracast receiver is implemented but **real Galaxy end-to-end testing is still pending**. Your Linux driver must advertise **P2P-client/P2P-GO** modes. Starting it may disconnect the *selected* Wi-Fi adapter, after your explicit approval.
- **Virtual camera:** A real 1920×1080 output has been verified. AirPlay's *input* is still fitted into a 1280×720 canvas; a 1080p output does not mean native 1080p AirPlay input.
- **Audio:** AirPlay audio is routed to Ubuntu's selected desktop output, **not** embedded in the virtual camera. To capture it in OBS, use Desktop Audio or an appropriate output-capture source. Physical-device audio/sync verification is still pending.
- **Privacy:** No cloud service, account, or default screen recording. Your framing/settings are saved locally; pairing codes and network-disconnection consent are not saved.

### Tips

- **Camera not showing in OBS?** Check Kagami's **Check** status, then confirm the named virtual camera exists. The usual output is `/dev/video10`; the internal screen input is usually `/dev/video11`. The installer can select other free numbers.
- **Changing 720p ↔ 1080p?** Stop Kagami → deactivate or close the OBS/Discord camera consumer → select the new size → Start Kagami → reactivate the source. An open consumer can lock the previous resolution.
- **Phone is portrait?** Crop away the side borders. Stop/restart and update the crop after rotating the phone.
- **Smart View fails the P2P check?** This is often a **Linux driver capability** limitation, not proof the Wi-Fi hardware cannot do Miracast. The author's RTL8821CE with `rtw88_8821ce` currently does not advertise the required modes.
- **Protected content or app overlays?** Kagami mirrors the visible/capturable phone screen, not a direct camera sensor feed. Protected surfaces may appear black, and overlays inside the crop remain visible.

<details>
<summary><strong>More help · Updates, repair, and rollback</strong></summary>

Run the **same install command** above to update. The installer checks the active commit and skips unnecessary work; your settings are kept.

To inspect installed versions or switch back to the previous app version:

~~~bash
~/.local/bin/kagami versions
~/.local/bin/kagami rollback
~~~

To repeat system setup after a kernel change, module problem, or Secure Boot enrollment:

~~~bash
curl -fsSL https://github.com/celestial-sora/kagami/releases/latest/download/install-kagami.sh | bash -s -- --repair
~~~

For Secure Boot, follow the prompted **Enroll MOK** steps after reboot. App rollback does not roll back shared system packages, drivers, or backend dependencies.

Detailed guides: [Installation](docs/installation.md) · [AirPlay](docs/airplay-ubuntu.md) · [Smart View](docs/smartview-ubuntu.md) · [ADB](docs/receiver-setup.md) · [Hardware testing](docs/receiver-testing.md) · [Validation status](docs/validation.md).

</details>

</details>

<details>
<summary><strong>🇹🇭 ภาษาไทย · เปิดคู่มือการใช้งาน</strong></summary>

### เริ่มใช้งาน

1. เปิดแอป **Kagami** จากเมนูแอปพลิเคชันของ Ubuntu
2. เลือกวิธีเชื่อมต่อ แล้วกดปุ่ม **Check** ของโหมดนั้นก่อน
3. กด **Start** ใน Kagami หากใช้การเชื่อมต่อไร้สาย ชื่ออุปกรณ์จะเริ่มปรากฏให้ค้นหาในขั้นตอนนี้
4. เชื่อมต่อโทรศัพท์ตามวิธีในตารางด้านล่าง
5. ลากเลือกพื้นที่ภาพที่ต้องการ (**Crop**) แล้วปรับการหมุน กลับด้าน หรือความละเอียดได้ตามต้องการ
6. เปิด OBS เพิ่มแหล่งภาพ **Video Capture Device (V4L2)** แล้วเลือก **Kagami Virtual Camera** เมื่อเลิกใช้ให้กด **Stop** ใน Kagami

### เลือกวิธีเชื่อมต่อ

| โหมด | ทำบนโทรศัพท์ / อุปกรณ์ | สิ่งที่ต้องมี |
| :--- | :--- | :--- |
| **AirPlay** | iPhone / iPad / Mac → **Screen Mirroring** → **Kagami** | อยู่ในเครือข่าย LAN เดียวกัน และใช้ Avahi/mDNS ได้ |
| **Samsung Smart View** | Galaxy → **Smart View** → **Kagami** | อะแดปเตอร์และไดรเวอร์ Linux ที่รองรับ Wi-Fi Direct (P2P client/GO); ยังอยู่ในขั้นทดลอง |
| **USB Mirror** | เสียบสาย Android และอนุญาต **USB debugging** | สายรับส่งข้อมูล, ADB ที่อนุญาตแล้ว และ scrcpy 3.0+ |
| **Wi-Fi ADB Mirror** | เปิด **Wireless debugging** แล้ว Pair/Connect ผ่าน Kagami | เครือข่ายส่วนตัวที่เชื่อถือได้, ADB และ scrcpy 3.0+ |

**ควรเริ่มจากอะไรดี?** หากใช้ iPhone หรือ iPad ให้เริ่มจาก **AirPlay** ส่วน Galaxy ให้ลอง **Smart View** เมื่อไดรเวอร์ Wi-Fi รองรับ P2P ถ้า Smart View ใช้ไม่ได้ ยังมี USB/ADB เป็นทางเลือก โดย **ADB และ scrcpy ต้องติดตั้งแยก** ไม่ได้รวมอยู่ในตัวติดตั้งหลัก

### สถานะการใช้งานปัจจุบัน

- **AirPlay:** ทดสอบ iPad จริงบน Ubuntu 26.04 แล้ว ภาพปรากฏทั้งใน Kagami และ OBS แต่ยังไม่ได้ยืนยันกับ iPhone/Mac ทุกรุ่น การเชื่อมต่อซ้ำ และการเปิดหน้าจอนิ่งเป็นเวลานาน
- **Smart View:** มีตัวรับ Miracast แล้ว แต่ **ยังไม่ได้ยืนยันการทำงานครบขั้นตอนกับ Galaxy จริง** ไดรเวอร์ต้องรองรับ **P2P-client/P2P-GO** และอะแดปเตอร์ Wi-Fi ที่เลือกอาจหลุดจากเครือข่ายเดิมเมื่อเริ่มรับภาพ โดย Kagami จะขอความยินยอมก่อน
- **Virtual Camera:** ทดสอบการส่งออกภาพที่ 1920×1080 ได้จริงแล้ว แต่ AirPlay ใช้ภาพต้นทางที่จัดลงกรอบ 1280×720 การตั้งเอาต์พุต 1080p จึงไม่ใช่การรับ AirPlay แบบ Native 1080p
- **เสียง:** เสียง AirPlay ส่งไปยังอุปกรณ์เสียงที่ Ubuntu เลือก ไม่ได้รวมอยู่ใน Virtual Camera หากต้องการเสียงใน OBS ให้ตั้ง **Desktop Audio** หรือ Audio Output Capture เพิ่ม การทดสอบเสียงและความตรงกันของภาพ/เสียงกับ iPad จริงยังไม่ครบ
- **ความเป็นส่วนตัว:** ไม่มี Cloud ไม่มีบัญชี และไม่บันทึกหน้าจอเป็นไฟล์โดยอัตโนมัติ การตั้งค่าภาพจะถูกเก็บไว้ในเครื่อง แต่ไม่เก็บรหัส Pairing หรือคำยินยอมให้ตัดการเชื่อมต่อ Wi-Fi

### เจอปัญหา? ลองดูตรงนี้

- **OBS ไม่เจอกล้อง:** ตรวจสถานะปุ่ม **Check** และดูว่ามี Virtual Camera แล้วหรือยัง โดยปกติเอาต์พุตคือ `/dev/video10` ส่วน `/dev/video11` เป็นช่องภาพภายใน โปรแกรมติดตั้งอาจเลือกหมายเลขอื่นเมื่อมีอุปกรณ์ใช้ช่องเดิมอยู่
- **ปรับจาก 720p เป็น 1080p ไม่ได้:** กด Stop → ปิด/พักการใช้งานกล้องใน OBS หรือ Discord → เปลี่ยนความละเอียด → กด Start → เปิดใช้งานกล้องอีกครั้ง เพราะโปรแกรมที่จับกล้องอยู่สามารถล็อกความละเอียดเดิมไว้ได้
- **ภาพมือถือแนวตั้งมีขอบดำ:** ใช้ Crop ตัดขอบออก และหลังหมุนโทรศัพท์ควร Stop/Start ใหม่พร้อมปรับ Crop อีกครั้ง
- **Smart View แจ้งว่า P2P ไม่พร้อม:** อาจเกิดจาก **ไดรเวอร์ Linux** ไม่ประกาศความสามารถ P2P ไม่ได้แปลว่าชิป Wi-Fi ไม่มีความสามารถนี้เสมอไป เช่น RTL8821CE ที่ใช้ไดรเวอร์ `rtw88_8821ce` บนเครื่องพัฒนายังไม่ผ่านเงื่อนไขนี้
- **บางแอปขึ้นภาพดำหรือมีปุ่มติดภาพ:** Kagami รับภาพหน้าจอที่ระบบยอมให้ Mirror ไม่ใช่ภาพดิบจากกล้องมือถือ แอปที่ป้องกันการจับภาพอาจแสดงสีดำ และปุ่มที่อยู่ภายในพื้นที่ Crop จะยังติดมาด้วย

<details>
<summary><strong>ข้อมูลเพิ่มเติม · อัปเดต ซ่อมการติดตั้ง และย้อนเวอร์ชัน</strong></summary>

หากต้องการ **อัปเดต** ให้รันคำสั่งติดตั้งด้านบนซ้ำได้เลย ตัวติดตั้งจะตรวจเวอร์ชันก่อนและข้ามงานที่ไม่จำเป็น พร้อมเก็บการตั้งค่าเดิมไว้

ดูเวอร์ชันและย้อนกลับไปยังเวอร์ชันแอปก่อนหน้า:

~~~bash
~/.local/bin/kagami versions
~/.local/bin/kagami rollback
~~~

หากเปลี่ยน Kernel, มีปัญหาไดรเวอร์ หรือเพิ่งจัดการ Secure Boot ให้รันคำสั่งซ่อม:

~~~bash
curl -fsSL https://github.com/celestial-sora/kagami/releases/latest/download/install-kagami.sh | bash -s -- --repair
~~~

ถ้า Secure Boot ขอให้ลงทะเบียนคีย์ ให้รีบูตแล้วทำขั้นตอน **Enroll MOK** ตามคำแนะนำ การ Rollback จะย้อนเฉพาะตัวแอป ไม่ได้ย้อนแพ็กเกจ ไดรเวอร์ หรือ Backend ที่ติดตั้งร่วมกัน

คู่มือเพิ่มเติม: [ติดตั้ง](docs/installation.md) · [AirPlay](docs/airplay-ubuntu.md) · [Smart View](docs/smartview-ubuntu.md) · [ADB](docs/receiver-setup.md) · [ทดสอบอุปกรณ์](docs/receiver-testing.md) · [สถานะการทดสอบ](docs/validation.md)

</details>

</details>

## For developers / สำหรับนักพัฒนา

<details>
<summary><strong>Show development and test commands / แสดงคำสั่งสำหรับนักพัฒนา</strong></summary>

Kagami's desktop receiver is built with **Python, GTK4, GStreamer, and V4L2**. Smart View uses a separately built MiracleCast receiver; AirPlay uses a pinned and patched UxPlay receiver. Both retain their own upstream licenses.

~~~bash
python3 -m unittest discover -s tests -v
KAGAMI_TEST_GST=1 G_DEBUG=fatal-criticals python3 -m unittest discover -s tests -v
xvfb-run -a python3 tools/check_receiver_desktop.py
bash tools/run-receiver.sh airplay-doctor
bash tools/run-receiver.sh smartview-doctor --interface YOUR_WIFI_INTERFACE
~~~

These automated tests are **not** a substitute for real-device compatibility testing. See the [architecture](docs/architecture.md), [testing notes](docs/testing.md), [validation results](docs/validation.md), and [developer handoff](docs/handoff.md).

</details>

---

**License:** [MIT](LICENSE) for Kagami's source. Third-party components such as [UxPlay](https://github.com/FDH2/UxPlay) and [MiracleCast](https://github.com/albfan/miraclecast) keep their respective licenses.
