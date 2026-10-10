"""GTK4 reference desktop: source crop selection plus actual processed preview."""

import signal
import threading

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


class Window(Gtk.ApplicationWindow):
    def __init__(self, app, config, interface="wlo1", preferred_transport="smartview"):
        super().__init__(application=app, title="Kagami · 鏡", default_width=1040, default_height=800)
        self.receiver, self.presets = Receiver(config), Presets()
        self.items, self.busy, self.closing = [], False, False
        self.crop, self.frame, self.drag_start = Crop(), None, None
        self.loaded_key = None
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for name in ("top", "bottom", "start", "end"):
            getattr(body, "set_margin_" + name)(20)
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(body)
        self.set_child(scroll)
        heading = Gtk.Label(label="Kagami · Phone screen → Virtual Camera", xalign=0)
        heading.add_css_class("title-1")
        body.append(heading)
        body.append(self.label("Open Samsung Camera, TikTok, or your preferred app on the phone. Drag over its preview to crop."))
        modes = Gtk.Box(spacing=10)
        self.mode = Gtk.DropDown.new_from_strings(["Samsung Smart View (experimental)", "AirPlay · iPhone / iPad / Mac (experimental)", "USB Mirror (fallback)", "Wi-Fi ADB Mirror"])
        self.device = Gtk.DropDown.new_from_strings(["Refresh to find authorized Android devices"])
        self.device.set_hexpand(True)
        self.refresh = Gtk.Button(label="Refresh devices")
        self.refresh.connect("clicked", lambda _: self.run_task(devices, self.show_devices))
        for widget in (self.mode, self.device, self.refresh):
            modes.append(widget)
        body.append(modes)
        self.adb_info = self.label("USB: enable Developer options → USB debugging, unlock the phone, and accept its authorization prompt.")
        body.append(self.adb_info)
        body.append(self.label("Smart View: Galaxy → Smart View → Kagami. AirPlay: same local network → Screen Mirroring → Kagami."))
        smart = Gtk.Box(spacing=8)
        self.interface = Gtk.Entry(text=interface, placeholder_text="P2P Wi-Fi interface")
        self.allow_disconnect = Gtk.CheckButton(label="Allow this adapter to disconnect while receiving")
        check_smart = Gtk.Button(label="Check Smart View")
        check_smart.connect("clicked", self.check_smartview)
        for widget in (self.interface, self.allow_disconnect, check_smart):
            smart.append(widget)
        body.append(smart)
        check_air = Gtk.Button(label="Check AirPlay")
        check_air.connect("clicked", lambda _: self.run_task(airplay_preflight, lambda checks: self.status.set_text(" · ".join(f"{c['name']}: {c['detail']}" for c in checks))))
        body.append(check_air)
        wireless = Gtk.Expander(label="Android Wireless debugging — explicit pairing and connection")
        wifi = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        wifi.append(self.label("Enable Wireless debugging on a trusted local network. Pairing and connection use different ports from the Android screen."))
        row = Gtk.Box(spacing=8)
        self.pair_address = Gtk.Entry(placeholder_text="Pairing IP:port")
        self.code = Gtk.PasswordEntry(show_peek_icon=True)
        self.pair_button = Gtk.Button(label="Pair")
        self.pair_button.connect("clicked", self.pair_phone)
        for widget in (self.pair_address, self.code, self.pair_button):
            row.append(widget)
        wifi.append(row)
        row = Gtk.Box(spacing=8)
        self.address = Gtk.Entry(placeholder_text="Debugging IP:port")
        self.connect_button = Gtk.Button(label="Connect")
        self.connect_button.connect("clicked", self.connect_phone)
        row.append(self.address)
        row.append(self.connect_button)
        wifi.append(row)
        wireless.set_child(wifi)
        body.append(wireless)
        self.transport_panels = smart, check_air, wireless
        row = Gtk.Box(spacing=8)
        self.source = Gtk.Entry(text=config.source)
        self.output = Gtk.Entry(text=config.device)
        self.sizes = [(1280, 720), (960, 720), (720, 720), (720, 1280), (1920, 1080)]
        size_labels = ["1280×720 · 16:9", "960×720 · 4:3", "720×720 · 1:1", "720×1280 · portrait", "1920×1080 · 16:9"]
        if (config.width, config.height) not in self.sizes:
            self.sizes.append((config.width, config.height))
            size_labels.append(f"{config.width}×{config.height} · custom")
        self.size = Gtk.DropDown.new_from_strings(size_labels)
        self.size.set_selected(self.sizes.index((config.width, config.height)))
        self.fps = Gtk.SpinButton.new_with_range(1, 60, 1)
        self.fps.set_value(config.fps)
        for widget in (self.label("Input"), self.source, self.label("Output"), self.output, self.size, self.fps):
            row.append(widget)
        body.append(row)
        previews = Gtk.Box(spacing=12)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        column.set_hexpand(True)
        column.append(self.label("Phone screen — drag a crop rectangle"))
        overlay = Gtk.Overlay()
        self.screen = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.screen.set_size_request(360, 340)
        overlay.set_child(self.screen)
        self.drawing = Gtk.DrawingArea()
        self.drawing.set_draw_func(self.draw_crop)
        overlay.add_overlay(self.drawing)
        gesture = Gtk.GestureDrag()
        gesture.connect("drag-begin", self.drag_begin)
        gesture.connect("drag-update", self.drag_update)
        gesture.connect("drag-end", self.drag_end)
        self.drawing.add_controller(gesture)
        column.append(overlay)
        previews.append(column)
        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        column.set_hexpand(True)
        column.append(self.label("Virtual camera framing"))
        self.processed = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        self.processed.set_size_request(360, 340)
        column.append(self.processed)
        previews.append(column)
        body.append(previews)
        controls = Gtk.Box(spacing=8)
        self.aspect = Gtk.DropDown.new_from_strings(["Free crop", "16:9", "4:3", "1:1", "Portrait 9:16"])
        self.aspect.connect("notify::selected", self.preset_crop)
        self.rotation = Gtk.DropDown.new_from_strings(["0°", "90°", "180°", "270°"])
        self.mirror = Gtk.CheckButton(label="Mirror")
        self.fit = Gtk.DropDown.new_from_strings(["Fit (letterbox)", "Fill (center crop)"])
        self.apply = Gtk.Button(label="Apply framing")
        self.apply.connect("clicked", lambda _: self.apply_framing())
        reset = Gtk.Button(label="Full screen")
        reset.connect("clicked", self.reset_crop)
        for widget in (self.aspect, self.rotation, self.mirror, self.fit, self.apply, reset):
            controls.append(widget)
        body.append(controls)
        body.append(self.label("Crop removes controls outside the rectangle. Overlays inside it remain. Stop/restart after changing phone orientation; AirPlay places the screen inside a fixed 1280×720 canvas."))
        row = Gtk.Box(spacing=8)
        self.app_name = Gtk.Entry(text="Samsung Camera", placeholder_text="Preset label (app name)")
        self.save = Gtk.Button(label="Save preset")
        self.save.connect("clicked", self.save_preset)
        row.append(self.app_name)
        row.append(self.save)
        body.append(row)
        row = Gtk.Box(spacing=8)
        self.start = Gtk.Button(label="Start / Reconnect")
        self.start.add_css_class("suggested-action")
        self.start.connect("clicked", self.start_receiver)
        self.stop = Gtk.Button(label="Stop")
        self.stop.connect("clicked", self.stop_receiver)
        row.append(self.start)
        row.append(self.stop)
        body.append(row)
        self.status = self.label("Stopped. Select two Kagami loopbacks; see docs/receiver-setup.md.")
        self.metrics = self.label("OBS / Discord consumer verification: pending manual check.")
        body.append(self.status)
        body.append(self.metrics)
        self.connect("close-request", self.close_window)
        self.timer = GLib.timeout_add(100, self.tick)
        self.signal_sources = [GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, value, self.signal_stop)
                               for value in (signal.SIGTERM, signal.SIGINT)]
        self.metric_tick = 0
        self.mode.connect("notify::selected", self.update_mode)
        self.mode.set_selected(("smartview", "airplay", "usb", "wifi").index(preferred_transport))
        self.update_mode()
        self.sensitivity()

    def update_mode(self, *_args):
        mode = self.mode.get_selected()
        smart, air, wireless = self.transport_panels
        smart.set_visible(mode == 0)
        air.set_visible(mode == 1)
        wireless.set_visible(mode == 3)
        for widget in (self.device, self.refresh, self.adb_info):
            widget.set_visible(mode >= 2)

    @staticmethod
    def label(text):
        return Gtk.Label(label=text, xalign=0, wrap=True, selectable=True)

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
            self.crop, self.frame, self.loaded_key = Crop(), None, None
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
        context.set_source_rgba(.35, .8, .65, 1)
        context.set_line_width(2)
        context.rectangle(x + self.crop.x*w, y + self.crop.y*h, self.crop.width*w, self.crop.height*h)
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
            self.loaded_key = Presets.key(self.receiver.transport.identity.serial, self.app_name.get_text(), self.frame)
            if self.receiver.transport.identity.connection in ("miracast", "airplay"):
                self.drawing.queue_draw()
                return GLib.SOURCE_CONTINUE
            try:
                preset = self.presets.load(self.receiver.transport.identity.serial, self.app_name.get_text(), self.frame)
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


def run(config, interface="wlo1", preferred_transport="smartview"):
    app = Gtk.Application(application_id="io.kagami.Receiver")
    app.connect("activate", lambda app: Window(app, config, interface, preferred_transport).present() if not app.get_active_window() else app.get_active_window().present())
    return app.run([])
