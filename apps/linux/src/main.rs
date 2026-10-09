//! Native start/stop/pairing shell. The media helper is intentionally a Phase 0
//! seam, to be replaced with gstreamer-rs after the Fedora hardware proof.

use adw::prelude::*;
use gtk::{gdk, glib};
use qrcode::{Color, QrCode};
use serde_json::Value;
use std::cell::{Cell, RefCell};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::rc::Rc;
use std::sync::mpsc;
use std::time::{Duration, Instant};

struct Host {
    child: Child,
    events: mpsc::Receiver<String>,
    stop_started: Option<Instant>,
}

impl Host {
    fn start(root: &Path, config: &Path) -> std::io::Result<Self> {
        let config = config.canonicalize()?;
        let python = std::env::var("KAGAMI_PYTHON").unwrap_or_else(|_| "python3".into());
        let mut child = Command::new(python)
            .args(["-u", "-m", "kagami_host", "serve", "--config"])
            .arg(config)
            .env("PYTHONPATH", root.join("apps/host"))
            .current_dir(root)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()?;
        let stdout = child.stdout.take().expect("stdout configured as piped");
        let (sender, events) = mpsc::sync_channel(64);
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().map_while(Result::ok) {
                if sender.send(line).is_err() {
                    break;
                }
            }
        });
        Ok(Self { child, events, stop_started: None })
    }

    fn stop(&mut self) {
        if self.stop_started.is_none() {
            self.stop_started = Some(Instant::now());
            // Signal our own child, allowing its HTTPS and GStreamer cleanup.
            unsafe { libc::kill(self.child.id() as libc::pid_t, libc::SIGTERM); }
        }
    }
}

impl Drop for Host {
    fn drop(&mut self) {
        if !matches!(self.child.try_wait(), Ok(Some(_))) {
            let _ = self.child.kill();
            let _ = self.child.wait();
        }
    }
}

fn qr_texture(text: &str) -> Result<gdk::MemoryTexture, qrcode::types::QrError> {
    let qr = QrCode::new(text.as_bytes())?;
    let scale = 4usize;
    let side = (qr.width() + 8) * scale;
    let mut pixels = vec![255u8; side * side * 4];
    for y in 0..qr.width() {
        for x in 0..qr.width() {
            if qr[(x, y)] == Color::Dark {
                for dy in 0..scale {
                    for dx in 0..scale {
                        let offset = (((y + 4) * scale + dy) * side + (x + 4) * scale + dx) * 4;
                        pixels[offset..offset + 3].fill(20);
                    }
                }
            }
        }
    }
    let bytes = glib::Bytes::from_owned(pixels);
    Ok(gdk::MemoryTexture::new(side as i32, side as i32, gdk::MemoryFormat::R8g8b8a8, &bytes, side * 4))
}

fn build(app: &adw::Application, root: PathBuf) {
    if let Some(window) = app.active_window() {
        window.present();
        return;
    }
    let window = adw::ApplicationWindow::builder()
        .application(app).title("Kagami · 鏡").default_width(560).default_height(650).build();
    let shell = gtk::Box::new(gtk::Orientation::Vertical, 0);
    shell.append(&adw::HeaderBar::new());
    let body = gtk::Box::new(gtk::Orientation::Vertical, 18);
    body.set_margin_top(20);
    body.set_margin_bottom(28);
    body.set_margin_start(32);
    body.set_margin_end(32);
    let title = gtk::Label::new(Some("kagami  鏡"));
    title.add_css_class("title-1");
    body.append(&title);
    let subtitle = gtk::Label::new(Some("Your phone. Your point of view."));
    subtitle.add_css_class("dim-label");
    body.append(&subtitle);
    let config = gtk::Entry::builder().text("config.json").placeholder_text("Configuration file").build();
    body.append(&gtk::Label::new(Some("Host configuration")));
    body.append(&config);
    let status = gtk::Label::new(Some("Host stopped"));
    status.set_wrap(true);
    body.append(&status);
    let picture = gtk::Picture::new();
    picture.set_size_request(230, 230);
    picture.set_can_shrink(true);
    picture.set_visible(false);
    body.append(&picture);
    let url = gtk::Label::new(None);
    url.set_wrap(true);
    url.set_selectable(true);
    body.append(&url);
    let detail = gtk::Label::new(Some("Complete the one-time TLS and virtual camera setup first."));
    detail.set_wrap(true);
    detail.add_css_class("dim-label");
    body.append(&detail);
    let start = gtk::Button::with_label("Start host");
    start.add_css_class("suggested-action");
    let stop = gtk::Button::with_label("Stop host");
    stop.set_sensitive(false);
    body.append(&start);
    body.append(&stop);
    let hint = gtk::Label::new(Some("In OBS: Video Capture Device → Kagami Virtual Camera"));
    hint.set_wrap(true);
    hint.add_css_class("dim-label");
    body.append(&hint);
    shell.append(&body);
    let scroll = gtk::ScrolledWindow::builder().hscrollbar_policy(gtk::PolicyType::Never).child(&shell).build();
    window.set_content(Some(&scroll));

    let host: Rc<RefCell<Option<Host>>> = Rc::new(RefCell::new(None));
    let closing = Rc::new(Cell::new(false));
    {
        let (host, config, status, detail, stop, picture, url) =
            (host.clone(), config.clone(), status.clone(), detail.clone(), stop.clone(), picture.clone(), url.clone());
        start.connect_clicked(move |button| {
            match Host::start(&root, &root.join(config.text().as_str())) {
                Ok(process) => {
                    *host.borrow_mut() = Some(process);
                    button.set_sensitive(false);
                    config.set_sensitive(false);
                    stop.set_sensitive(true);
                    status.set_text("Starting local host…");
                    detail.set_text("");
                    picture.set_visible(false);
                    url.set_text("");
                }
                Err(error) => status.set_text(&format!("Cannot start host: {error}")),
            }
        });
    }
    {
        let (host, status, url, picture) = (host.clone(), status.clone(), url.clone(), picture.clone());
        stop.connect_clicked(move |button| {
            if let Some(process) = host.borrow_mut().as_mut() {
                process.stop();
                status.set_text("Stopping host…");
                button.set_sensitive(false);
                picture.set_visible(false);
                url.set_text("");
            }
        });
    }
    {
        let (host, closing) = (host.clone(), closing.clone());
        window.connect_close_request(move |_| {
            if let Some(process) = host.borrow_mut().as_mut() {
                closing.set(true);
                process.stop();
                glib::Propagation::Stop
            } else {
                glib::Propagation::Proceed
            }
        });
    }
    let weak_window = window.downgrade();
    let mut pairing_until: Option<Instant> = None;
    glib::timeout_add_local(Duration::from_millis(100), move || {
        let Some(window) = weak_window.upgrade() else { return glib::ControlFlow::Break; };
        let mut exited = None;
        if let Some(process) = host.borrow_mut().as_mut() {
            while let Ok(line) = process.events.try_recv() {
                if let Ok(data) = serde_json::from_str::<Value>(&line) {
                    match data["event"].as_str() {
                        Some("ready") => {
                            if let Some(pair) = data["pair_url"].as_str() {
                                url.set_text(pair);
                                match qr_texture(pair) {
                                    Ok(texture) => { picture.set_paintable(Some(&texture)); picture.set_visible(true); }
                                    Err(error) => detail.set_text(&format!("Use the URL; QR creation failed: {error}")),
                                }
                                pairing_until = Some(Instant::now() + Duration::from_secs(300));
                            }
                            status.set_text("Waiting for your phone");
                            detail.set_text("Scan the QR code after trusting this host's local certificate. Pairing expires in 5 minutes.");
                        }
                        Some("paired") => { pairing_until = None; picture.set_visible(false); url.set_text(""); detail.set_text("Phone paired. Start its camera."); }
                        Some("metrics") => {
                            let state = data["state"].as_str().unwrap_or("waiting");
                            status.set_text(&format!("Camera: {state} · input {} fps · output {} fps", data["incoming_fps"], data["output_fps"]));
                        }
                        Some("error") => { status.set_text("Host needs attention"); detail.set_text(data["message"].as_str().unwrap_or("Check host diagnostics.")); }
                        _ => {}
                    }
                }
            }
            if process.stop_started.is_some_and(|when| when.elapsed() > Duration::from_secs(5)) {
                let _ = process.child.kill();
            }
            match process.child.try_wait() {
                Ok(Some(result)) => exited = Some(result.success()),
                Err(error) => { detail.set_text(&error.to_string()); exited = Some(false); }
                _ => {}
            }
        }
        if pairing_until.is_some_and(|deadline| Instant::now() >= deadline) {
            pairing_until = None;
            picture.set_visible(false);
            url.set_text("");
            detail.set_text("Pairing expired. Stop and restart the host for a fresh QR code.");
        }
        if let Some(success) = exited {
            host.borrow_mut().take();
            start.set_sensitive(true);
            config.set_sensitive(true);
            stop.set_sensitive(false);
            picture.set_visible(false);
            url.set_text("");
            status.set_text(if success { "Host stopped" } else { "Host stopped; check the message above" });
            if closing.get() { window.close(); return glib::ControlFlow::Break; }
        }
        glib::ControlFlow::Continue
    });
    window.present();
}

fn main() -> glib::ExitCode {
    let root = std::env::var_os("KAGAMI_ROOT").map(PathBuf::from)
        .unwrap_or_else(|| Path::new(env!("CARGO_MANIFEST_DIR")).join("../.."));
    let app = adw::Application::builder().application_id("io.kagami.Host").build();
    app.connect_activate(move |app| build(app, root.clone()));
    app.run()
}
