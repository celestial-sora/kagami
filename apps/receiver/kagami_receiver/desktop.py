"""GTK4 reference desktop: source crop selection plus actual processed preview."""

import signal
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_foreign("cairo")
from gi.repository import Gdk, GLib, Gtk

from .controller import Receiver
from .model import Crop, Framing, OutputConfig, Presets, content_rect, drag_crop, centered_crop
from .transport import ScrcpyTransport, connect, devices, pair
from .smartview import SmartViewTransport, preflight
from .airplay import AirPlayTransport, preflight as airplay_preflight
from .settings import DesktopPreferences, Settings, TRANSPORTS


class Window(Gtk.ApplicationWindow):
    def __init__(self, app, config, interface="wlo1", preferred_transport="smartview", *, settings=None,
                 preferences=None, settings_error=None):
        super().__init__(application=app, title="Kagami · 鏡", default_width=1360, default_height=1040)
        Gtk.IconTheme.get_for_display(self.get_display()).add_search_path(str(Path(__file__).resolve().parent / "icons"))
        self.set_icon_name("io.kagami.Host")
        self.set_size_request(980, 520)
        self.settings = settings or Settings()
        self.save_timer = None
        if preferences is None:
            preferences = DesktopPreferences(config, interface, preferred_transport)
            try:
                preferences = self.settings.load(preferences)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                settings_error = str(exc)
        config, interface, preferred_transport = preferences.output, preferences.interface, preferences.transport
        self.settings_blocked = settings_error is not None
        self.receiver, self.presets = Receiver(config), Presets()
        self.receiver.framing = preferences.framing
        self.items, self.busy, self.closing = [], False, False
        self.crop, self.frame, self.drag_start = preferences.framing.crop, None, None
        self.loaded_key = None
        self.add_css_class("kagami")
        provider = Gtk.CssProvider()
        provider.load_from_path(str(Path(__file__).with_name("desktop.css")))
        Gtk.StyleContext.add_provider_for_display(self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        for edge in ("top", "bottom", "start", "end"):
            getattr(shell, "set_margin_" + edge)(18)
        self.set_child(shell)
        header = Gtk.Box(spacing=18)
        logo = self.icon("brand", 76)
        logo.add_css_class("brand-icon")
        header.append(logo)
        brand = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        title = self.label("Kagami · 鏡")
        title.add_css_class("brand-title")
        brand.append(title)
        subtitle = self.label("Phone screen → Virtual Camera")
        subtitle.add_css_class("subtitle")
        brand.append(subtitle)
        brand.set_hexpand(True)
        header.append(brand)
        self.start = Gtk.Button(label="Start / Reconnect")
        self.start.add_css_class("suggested-action")
        self.start.connect("clicked", self.start_receiver)
        self.stop = Gtk.Button(label="Stop")
        self.stop.connect("clicked", self.stop_receiver)
        self.start.set_valign(Gtk.Align.CENTER)
        self.stop.set_valign(Gtk.Align.CENTER)
        header.append(self.start)
        header.append(self.stop)
        settings_button = Gtk.Button(icon_name="emblem-system-symbolic")
        settings_button.add_css_class("settings-button")
        settings_button.set_tooltip_text("Show connection setup and framing controls")
        settings_button.set_valign(Gtk.Align.CENTER)
        header.append(settings_button)
        shell.append(header)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_vexpand(True)
        shell.append(scroll)
        columns = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        columns.add_css_class("columns")
        columns.set_position(540)
        columns.set_resize_start_child(False)
        columns.set_shrink_start_child(False)
        columns.set_shrink_end_child(False)
        scroll.set_child(columns)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        left.set_size_request(540, -1)
        left.set_hexpand(False)
        right.set_hexpand(True)
        columns.set_start_child(left)
        columns.set_end_child(right)

        source_panel = self.panel("Connection Source")
        left.append(source_panel)
        self.mode = Gtk.DropDown.new_from_strings(["Samsung Smart View", "AirPlay", "USB Mirror", "Wi-Fi ADB Mirror"])
        cards = Gtk.Box(spacing=12, homogeneous=True)
        self.source_cards = []
        for name, detail, icon, mode in (("AirPlay", "iPhone / iPad / Mac", "airplay", 1),
                                         ("Smart View", "Samsung / Android", "cast", 0)):
            button = Gtk.Button()
            button.add_css_class("source-card")
            content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            top = Gtk.Box(spacing=12)
            symbol = self.icon(icon, 48)
            top.append(symbol)
            dot = Gtk.Label(label="○", hexpand=True, xalign=1)
            top.append(dot)
            content.append(top)
            text = self.label(name)
            text.add_css_class("card-title")
            content.append(text)
            text = self.label(detail)
            text.add_css_class("subtitle")
            content.append(text)
            button.set_child(content)
            button.connect("clicked", lambda _, selected=mode: self.mode.set_selected(selected))
            self.source_cards.append((button, dot, mode))
            cards.append(button)
        source_panel.append(cards)
        self.status = self.label("Not connected")
        self.status.add_css_class("connection-status")
        self.status.set_max_width_chars(48)
        status_panel = self.panel()
        status_panel.add_css_class("status-panel")
        self.connection_title = self.label("●  Not connected")
        self.connection_title.add_css_class("status-title")
        status_panel.append(self.connection_title)
        status_panel.append(self.status)
        left.append(status_panel)

        camera = self.panel()
        camera_header = Gtk.Box(spacing=12)
        heading = self.label("Camera Settings")
        heading.add_css_class("section-title")
        heading.set_hexpand(True)
        camera_header.append(heading)
        reset = Gtk.Button(label="Reset")
        reset.add_css_class("flat")
        reset.connect("clicked", self.reset_crop)
        reset.set_tooltip_text("Reset crop to the full phone screen")
        camera_header.append(reset)
        camera.append(camera_header)
        self.source = Gtk.Entry(text=config.source)
        self.output = Gtk.Entry(text=config.device)
        self.source.set_tooltip_text("Kagami screen input loopback; never select a physical camera")
        self.output.set_tooltip_text("Kagami virtual camera loopback for OBS / apps")
        self.sizes = [(1280, 720), (960, 720), (720, 720), (720, 1280), (1920, 1080)]
        size_labels = ["1280 × 720 (16:9)", "960 × 720 (4:3)", "720 × 720 (1:1)", "720 × 1280 (portrait)", "1920 × 1080 (16:9)"]
        if (config.width, config.height) not in self.sizes:
            self.sizes.append((config.width, config.height))
            size_labels.append(f"{config.width} × {config.height} (custom)")
        self.size = Gtk.DropDown.new_from_strings(size_labels)
        self.size.set_selected(self.sizes.index((config.width, config.height)))
        self.size.set_tooltip_text("Stop Kagami and release the camera in OBS/Discord before changing size.")
        self.fps = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.fps.set_value(config.fps)
        for icon, label, widget in (("camera-video-symbolic", "Input", self.source),
                                     ("camera-photo-symbolic", "Output", self.output),
                                     ("video-display-symbolic", "Resolution", self.size),
                                     ("flash", "Framerate", self.fps)):
            row = Gtk.Box(spacing=12)
            image = self.icon("flash", 22) if icon == "flash" else Gtk.Image.new_from_icon_name(icon)
            image.set_pixel_size(22)
            row.append(image)
            label_widget = self.label(label)
            label_widget.set_size_request(95, -1)
            row.append(label_widget)
            widget.set_hexpand(True)
            row.append(widget)
            if widget is self.fps:
                row.append(self.label("FPS"))
            camera.append(row)
        left.append(camera)

        options = self.panel("Preview Options")
        self.guide = Gtk.Switch()
        self.safe_area = Gtk.Switch()
        self.mirror = Gtk.Switch()
        self.mirror.add_css_class("mirror-toggle")
        for icon, label, widget in (("guide", "Show Framing Guide", self.guide), ("safe", "Show Safe Area (OBS)", self.safe_area),
                                     ("mirror", "Mirror Preview / Output", self.mirror)):
            row = Gtk.Box(spacing=12)
            row.append(self.icon(icon, 26))
            text = self.label(label)
            text.set_hexpand(True)
            row.append(text)
            row.append(widget)
            options.append(row)
        for widget in (self.guide, self.safe_area):
            widget.connect("notify::active", lambda *_: self.drawing.queue_draw())
        self.mirror.connect("notify::active", lambda *_: self.apply_framing())
        left.append(options)

        preview = self.panel()
        preview.add_css_class("preview-panel")
        preview_header = Gtk.Box(spacing=10)
        preview_header.append(Gtk.Image.new_from_icon_name("video-display-symbolic"))
        text = self.label("Live Preview")
        text.add_css_class("section-title")
        text.set_hexpand(True)
        preview_header.append(text)
        self.preview_badge = self.label("")
        self.preview_badge.add_css_class("preview-badge")
        preview_header.append(self.preview_badge)
        preview.append(preview_header)
        overlay = Gtk.Overlay()
        overlay.add_css_class("preview-canvas")
        overlay.set_size_request(380, 490)
        overlay.set_vexpand(True)
        self.screen = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        overlay.set_child(self.screen)
        self.preview_placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.preview_placeholder.set_halign(Gtk.Align.CENTER)
        self.preview_placeholder.set_valign(Gtk.Align.CENTER)
        symbol = Gtk.Image.new_from_icon_name("video-display-symbolic")
        symbol.set_pixel_size(64)
        self.preview_placeholder.append(symbol)
        text = self.label("Your phone screen appears here")
        text.add_css_class("card-title")
        self.preview_placeholder.append(text)
        self.preview_placeholder.append(self.label("Start receiving, then connect to Kagami."))
        self.preview_placeholder.set_can_target(False)
        overlay.add_overlay(self.preview_placeholder)
        self.drawing = Gtk.DrawingArea()
        self.drawing.set_draw_func(self.draw_crop)
        overlay.add_overlay(self.drawing)
        gesture = Gtk.GestureDrag()
        gesture.connect("drag-begin", self.drag_begin)
        gesture.connect("drag-update", self.drag_update)
        gesture.connect("drag-end", self.drag_end)
        self.drawing.add_controller(gesture)
        preview.append(overlay)
        right.append(preview)
        help_panel = self.panel("How to Use")
        steps = Gtk.Box(spacing=18, homogeneous=True)
        for number, title, text in (("1", "Start AirPlay / Smart View", "Start receiving, then open screen mirroring on your phone and connect to Kagami."),
                                    ("2", "Adjust Crop (Optional)", "Drag the preview to adjust framing. Apply crop in Framing controls."),
                                    ("3", "Use in OBS / Apps", "Select Kagami Virtual Camera as your camera. AirPlay audio uses Desktop Audio.")):
            step = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            badge = Gtk.Label(label=number, halign=Gtk.Align.START)
            badge.add_css_class("step-" + number)
            badge.add_css_class("step-number")
            step_top = Gtk.Box(spacing=24)
            step_top.append(badge)
            step_top.append(self.icon({"1": "airplay", "2": "crop", "3": "video"}[number], 40))
            step.append(step_top)
            title_widget = self.label(title)
            title_widget.add_css_class("step-title")
            step.append(title_widget)
            step.append(self.label(text))
            steps.append(step)
        help_panel.append(steps)
        right.append(help_panel)

        # Less frequent setup and framing controls remain available below the main view.
        advanced = Gtk.Expander(label="Connection setup & framing controls")
        advanced.add_css_class("advanced")
        setup = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        advanced.set_child(setup)
        left.append(advanced)
        setup.append(self.mode)
        self.device = Gtk.DropDown.new_from_strings(["Refresh to find authorized Android devices"])
        self.refresh = Gtk.Button(label="Refresh devices")
        self.refresh.connect("clicked", lambda _: self.run_task(devices, self.show_devices))
        setup.append(self.device)
        setup.append(self.refresh)
        self.adb_info = self.label("USB: enable USB debugging, unlock the phone and accept its authorization prompt.")
        setup.append(self.adb_info)
        smart = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.interface = Gtk.Entry(text=interface, placeholder_text="P2P Wi-Fi interface")
        self.allow_disconnect = Gtk.CheckButton(label="Allow this adapter to disconnect while receiving")
        check_smart = Gtk.Button(label="Check Smart View")
        check_smart.connect("clicked", self.check_smartview)
        for widget in (self.interface, self.allow_disconnect, check_smart):
            smart.append(widget)
        setup.append(smart)
        check_air = Gtk.Button(label="Check AirPlay")
        check_air.connect("clicked", lambda _: self.run_task(airplay_preflight, lambda checks: self.status.set_text(" · ".join(f"{c['name']}: {c['detail']}" for c in checks))))
        setup.append(check_air)
        wireless = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wireless.append(self.label("Android Wireless debugging: pairing and connection use different ports. Use a trusted network."))
        self.pair_address = Gtk.Entry(placeholder_text="Pairing IP:port")
        self.code = Gtk.PasswordEntry(show_peek_icon=True)
        self.pair_button = Gtk.Button(label="Pair")
        self.pair_button.connect("clicked", self.pair_phone)
        self.address = Gtk.Entry(placeholder_text="Debugging IP:port")
        self.connect_button = Gtk.Button(label="Connect")
        self.connect_button.connect("clicked", self.connect_phone)
        for widget in (self.pair_address, self.code, self.pair_button, self.address, self.connect_button):
            wireless.append(widget)
        setup.append(wireless)
        self.transport_panels = smart, check_air, wireless
        self.aspect = Gtk.DropDown.new_from_strings(["Free crop", "16:9", "4:3", "1:1", "Portrait 9:16"])
        self.rotation = Gtk.DropDown.new_from_strings(["0°", "90°", "180°", "270°"])
        self.fit = Gtk.DropDown.new_from_strings(["Fit (letterbox)", "Fill (center crop)"])
        self.apply = Gtk.Button(label="Apply framing")
        self.apply.connect("clicked", lambda _: self.apply_framing())
        for widget in (self.aspect, self.rotation, self.fit, self.apply):
            setup.append(widget)
        setup.append(self.label("Changing camera size: Stop → deactivate camera in OBS/Discord → choose size → Start → reactivate camera."))
        self.app_name = Gtk.Entry(text="Samsung Camera", placeholder_text="Preset label (app name)")
        self.save = Gtk.Button(label="Save preset")
        self.save.connect("clicked", self.save_preset)
        setup.append(self.app_name)
        setup.append(self.save)
        self.settings_status = self.label("Settings are saved automatically on this computer.")
        if settings_error:
            self.settings_status.set_text("Saved settings could not load; the file was kept: " + settings_error)
        setup.append(self.settings_status)
        self.metrics = self.label("OBS / Discord consumer verification: pending manual check.")
        setup.append(self.metrics)
        output_preview = Gtk.Expander(label="Virtual camera output preview")
        self.processed = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.processed.set_size_request(320, 180)
        output_preview.set_child(self.processed)
        right.append(output_preview)
        settings_button.connect("clicked", lambda _: advanced.set_expanded(not advanced.get_expanded()))
        self.connect("close-request", self.close_window)
        self.timer = GLib.timeout_add(100, self.tick)
        self.signal_sources = [GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, value, self.signal_stop)
                               for value in (signal.SIGTERM, signal.SIGINT)]
        self.metric_tick = 0
        self.mode.connect("notify::selected", self.update_mode)
        self.mode.set_selected(("smartview", "airplay", "usb", "wifi").index(preferred_transport))
        self.rotation.set_selected(preferences.framing.rotation // 90)
        self.mirror.set_active(preferences.framing.mirror)
        self.fit.set_selected(int(preferences.framing.fit == "fill"))
        self.aspect.set_selected(preferences.aspect)
        self.app_name.set_text(preferences.label)
        self.aspect.connect("notify::selected", self.preset_crop)
        for widget, event in ((self.source, "changed"), (self.output, "changed"), (self.interface, "changed"),
                              (self.app_name, "changed"), (self.size, "notify::selected"), (self.fps, "value-changed"),
                              (self.mode, "notify::selected"), (self.aspect, "notify::selected"),
                              (self.rotation, "notify::selected"), (self.mirror, "notify::active"), (self.fit, "notify::selected")):
            widget.connect(event, self.schedule_save)
        self.update_mode()
        self.sensitivity()

    @staticmethod
    def icon(name, size):
        image = Gtk.Image.new_from_file(str(Path(__file__).with_name("icons") / (name + ".svg")))
        image.set_pixel_size(size)
        return image

    def panel(self, title=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.add_css_class("panel")
        if title:
            label = self.label(title)
            label.add_css_class("section-title")
            box.append(label)
        return box

    def preferences(self):
        width, height = self.sizes[self.size.get_selected()]
        output = OutputConfig(self.source.get_text(), self.output.get_text(), width, height, self.fps.get_value_as_int())
        return DesktopPreferences(output, self.interface.get_text(), TRANSPORTS[self.mode.get_selected()],
                                  self.framing(), self.aspect.get_selected(), self.app_name.get_text())

    def schedule_save(self, *_args):
        if self.save_timer:
            GLib.source_remove(self.save_timer)
        self.save_timer = GLib.timeout_add(400, self.save_settings)

    def save_settings(self):
        if self.save_timer:
            GLib.source_remove(self.save_timer)
            self.save_timer = None
        if self.settings_blocked:
            self.settings_status.set_text(f"Settings were kept unchanged. Repair {self.settings.path} and reopen Kagami to save changes.")
            return GLib.SOURCE_REMOVE
        try:
            self.settings.save(self.preferences())
            self.settings_status.set_text("Settings saved on this computer.")
        except (ValueError, TypeError, KeyError, OSError) as exc:
            self.settings_status.set_text("Settings were not saved: " + str(exc))
        return GLib.SOURCE_REMOVE

    def update_mode(self, *_args):
        mode = self.mode.get_selected()
        for button, dot, selected in self.source_cards:
            dot.set_text("●" if mode == selected else "○")
            if mode == selected:
                button.add_css_class("selected")
            else:
                button.remove_css_class("selected")
        self.start.set_label(("Start Smart View", "Start AirPlay", "Start USB mirror", "Start Wi-Fi mirror")[mode])
        smart, air, wireless = self.transport_panels
        smart.set_visible(mode == 0)
        air.set_visible(mode == 1)
        wireless.set_visible(mode == 3)
        for widget in (self.device, self.refresh, self.adb_info):
            widget.set_visible(mode >= 2)
        if self.receiver.state == "stopped" and not self.busy:
            self.status.set_text("AirPlay is stopped. Click Start AirPlay, then select Kagami in Screen Mirroring on the same network."
                                 if mode == 1 else "Receiver is stopped. Check the selected connection, then click Start.")

    @staticmethod
    def label(text):
        return Gtk.Label(label=text, xalign=0, wrap=True, selectable=False)

    def run_task(self, task, complete):
        if self.busy:
            return
        self.busy = True
        self.status.set_text("Working…")
        self.sensitivity()
        def run():
            result, error = None, None
            try:
                result = task()
            except Exception as exc:
                error = str(exc)
            GLib.idle_add(finish, result, error)
        def finish(result, error):
            self.busy = False
            if self.closing:
                self.receiver.stop()
                self.destroy()
                return GLib.SOURCE_REMOVE
            if error:
                self.status.set_text(error)
            else:
                complete(result)
            self.sensitivity()
            return GLib.SOURCE_REMOVE
        threading.Thread(target=run, daemon=True, name="kagami-connection").start()

    def sensitivity(self):
        active = self.receiver.state in ("starting", "live", "waiting")
        for widget in (self.refresh, self.start, self.pair_button, self.connect_button):
            widget.set_sensitive(not self.busy and not active)
        for button, _dot, _mode in self.source_cards:
            button.set_sensitive(not self.busy and not active)
        self.connection_title.set_text("●  " + ("Working…" if self.busy else {
            "stopped": "Not connected", "starting": "Starting receiver", "waiting": "Waiting for phone",
            "live": "Connected", "disconnected": "Disconnected"
        }.get(self.receiver.state, self.receiver.state.capitalize())))
        width, height = self.sizes[self.size.get_selected()]
        self.preview_badge.set_text(f"{width} × {height} · {self.fps.get_value_as_int()} FPS")
        self.preview_placeholder.set_visible(self.screen.get_paintable() is None)
        self.stop.set_sensitive(not self.busy and self.receiver.state != "stopped")
        for widget in (self.source, self.output, self.size, self.fps, self.mode, self.device, self.interface, self.allow_disconnect):
            widget.set_sensitive(not self.busy and not active)

    def show_devices(self, values):
        self.items = values
        self.device.set_model(Gtk.StringList.new([f"{d.model} · {d.serial} · {d.connection} · {d.state}" for d in values] or ["No Android devices"]))
        self.status.set_text("Choose an authorized device. Unauthorized: accept the debugging prompt on your phone.")

    def pair_phone(self, _button):
        address, code = self.pair_address.get_text(), self.code.get_text()
        self.code.set_text("")
        self.run_task(lambda: pair(address, code), lambda text: self.status.set_text(text))

    def wifi_connected(self, text):
        self.status.set_text(text + " — select Wi-Fi Mirror and refresh devices.")

    def connect_phone(self, _button):
        address = self.address.get_text()
        self.run_task(lambda: connect(address), self.wifi_connected)

    def check_smartview(self, _button):
        interface = self.interface.get_text()
        self.run_task(lambda: preflight(interface), lambda checks: self.status.set_text(" · ".join(f"{c['name']}: {c['detail']}" for c in checks)))

    def start_receiver(self, _button):
        try:
            index = self.device.get_selected()
            mode = self.mode.get_selected()
            if mode >= 2 and index >= len(self.items):
                raise ValueError("Refresh and select an authorized Android device.")
            width, height = self.sizes[self.size.get_selected()]
            config = OutputConfig(self.source.get_text(), self.output.get_text(), width, height, self.fps.get_value_as_int())
            self.receiver.stop()
            self.receiver = Receiver(config)
            self.receiver.framing = self.framing()
            self.frame, self.loaded_key = None, None
            self.save_settings()
            if mode == 0:
                adapter = SmartViewTransport(self.interface.get_text(), allow_disconnect=self.allow_disconnect.get_active())
                message = "Open Smart View on the Galaxy and select Kagami."
            elif mode == 1:
                adapter = AirPlayTransport()
                message = "On iPhone/iPad/Mac, open Screen Mirroring and select Kagami on the same local network."
            else:
                adapter = ScrcpyTransport(self.items[index], "wifi" if mode == 3 else "usb")
                message = "Starting screen mirror…"
            self.run_task(lambda: self.receiver.start(adapter), lambda _: self.status.set_text(message))
        except (ValueError, RuntimeError, OSError) as exc:
            self.status.set_text(str(exc))

    def stop_receiver(self, _button):
        try:
            self.receiver.stop()
        except RuntimeError as exc:
            self.status.set_text(str(exc))
            self.sensitivity()
            return
        self.screen.set_paintable(None)
        self.processed.set_paintable(None)
        self.status.set_text("Stopped. The phone is no longer captured.")
        self.frame = None
        self.drawing.queue_draw()
        self.sensitivity()

    def framing(self):
        return Framing(self.crop, self.rotation.get_selected() * 90, self.mirror.get_active(), "fill" if self.fit.get_selected() else "fit")

    def apply_framing(self):
        self.schedule_save()
        if self.busy:
            return
        try:
            self.receiver.reframe(self.framing())
        except (ValueError, RuntimeError, OSError) as exc:
            self.status.set_text(str(exc))
        self.drawing.queue_draw()

    def reset_crop(self, _button):
        self.crop = Crop()
        self.aspect.set_selected(0)
        self.apply_framing()

    def preset_crop(self, *_args):
        if self.frame and self.aspect.get_selected():
            ratio = [None, 16/9, 4/3, 1, 9/16][self.aspect.get_selected()]
            self.crop = centered_crop(self.frame.width, self.frame.height, ratio)
            self.apply_framing()

    def save_preset(self, _button):
        if self.busy:
            return
        if not self.frame or not self.receiver.transport:
            self.status.set_text("Start mirroring before saving a device/orientation preset.")
            return
        if self.receiver.transport.identity.connection in ("miracast", "airplay"):
            self.status.set_text("Wireless phone identity is not verified yet. Saved device presets are available for authorized ADB devices.")
            return
        try:
            self.presets.save(self.receiver.transport.identity.serial, self.app_name.get_text(), self.frame, self.framing())
            self.status.set_text("Framing saved locally for this device, label and captured orientation.")
        except (ValueError, OSError) as exc:
            self.status.set_text(str(exc))

    def draw_crop(self, _area, context, width, height):
        if not self.frame:
            return
        x, y, w, h = content_rect(width, height, self.frame.width, self.frame.height)
        context.set_source_rgba(.9, .55, 1, 1)
        context.set_line_width(2)
        x, y, w, h = x + self.crop.x*w, y + self.crop.y*h, self.crop.width*w, self.crop.height*h
        context.rectangle(x, y, w, h)
        context.stroke()
        if self.guide.get_active():
            context.set_source_rgba(1, 1, 1, .35)
            context.set_line_width(1)
            for fraction in (1/3, 2/3):
                context.move_to(x + w*fraction, y)
                context.line_to(x + w*fraction, y + h)
                context.move_to(x, y + h*fraction)
                context.line_to(x + w, y + h*fraction)
            context.stroke()
        if self.safe_area.get_active():
            context.set_source_rgba(1, .75, 1, .7)
            context.set_dash([6, 4])
            context.rectangle(x + w*.05, y + h*.05, w*.9, h*.9)
            context.stroke()

    def drag_begin(self, _gesture, x, y):
        self.drag_start = (x, y)

    def drag_update(self, _gesture, dx, dy):
        if self.frame and self.drag_start:
            rect = content_rect(self.drawing.get_width(), self.drawing.get_height(), self.frame.width, self.frame.height)
            crop = drag_crop(self.drag_start, (self.drag_start[0] + dx, self.drag_start[1] + dy), rect)
            if crop:
                self.crop = crop
                self.drawing.queue_draw()

    def drag_end(self, gesture, dx, dy):
        self.drag_update(gesture, dx, dy)
        self.drag_start = None
        self.aspect.set_selected(0)
        self.apply_framing()

    def tick(self):
        if self.busy:
            return GLib.SOURCE_CONTINUE
        self.receiver.tick()
        if self.receiver.frame and self.loaded_key is None:
            self.frame = self.receiver.frame
            self.preset_crop()
            self.loaded_key = Presets.key(self.receiver.transport.identity.serial, self.app_name.get_text(), self.frame)
            if self.receiver.transport.identity.connection in ("miracast", "airplay"):
                self.drawing.queue_draw()
                return GLib.SOURCE_CONTINUE
            try:
                preset = self.presets.load(self.receiver.transport.identity.serial, self.app_name.get_text(), self.frame, default=None)
                if preset is not None:
                    self.crop = preset.crop
                    self.rotation.set_selected(preset.rotation // 90)
                    self.mirror.set_active(preset.mirror)
                    self.fit.set_selected(int(preset.fit == "fill"))
                    self.receiver.reframe(preset)
            except (ValueError, OSError) as exc:
                self.status.set_text("Preset could not load: " + str(exc))
        if self.receiver.processor:
            for name, (width, height, pixels) in self.receiver.processor.take_previews().items():
                texture = Gdk.MemoryTexture.new(width, height, Gdk.MemoryFormat.R8G8B8A8, GLib.Bytes.new(pixels), len(pixels) // height)
                (self.screen if name == "screen" else self.processed).set_paintable(texture)
        elif self.receiver.state == "disconnected":
            self.screen.set_paintable(None)
            self.processed.set_paintable(None)
            self.status.set_text(self.receiver.error_message + " — output is black; refresh and reconnect.")
        self.metric_tick += 1
        if self.metric_tick % 10 == 0:
            metrics = self.receiver.metrics()
            self.metrics.set_text(f"{metrics['state']} · {metrics['device']} · input {metrics['incoming_fps']} FPS · output {metrics['output_fps']} FPS · host pipeline {metrics.get('host_pipeline_ms', '—')} ms · rate drops {metrics.get('rate_dropped', 0)} · OBS/Discord check pending")
        self.sensitivity()
        return GLib.SOURCE_CONTINUE

    def close_window(self, _window):
        self.save_settings()
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = None
        for source in self.signal_sources:
            GLib.source_remove(source)
        self.signal_sources.clear()
        if self.busy:
            self.closing = True
            return True
        try:
            self.receiver.stop()
        except RuntimeError as exc:
            print(str(exc), flush=True)
        return False

    def signal_stop(self):
        self.close()
        return GLib.SOURCE_CONTINUE


def run(config, interface="wlo1", preferred_transport="smartview", **settings):
    app = Gtk.Application(application_id="io.kagami.Host")
    app.connect("activate", lambda app: Window(app, config, interface, preferred_transport, **settings).present() if not app.get_active_window() else app.get_active_window().present())
    return app.run([])
