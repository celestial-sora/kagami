"""Enter the packaged receiver without borrowing host Python modules."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(root / 'lib/python3/dist-packages'), str(root / 'share/kagami/apps/receiver')]
if sys.argv[1:2] in (['--appimage-check'], ['--appimage-gtk-check']):
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Gst', '1.0')
    gi.require_foreign('cairo')
    from gi.repository import Gtk, Gst
    Gst.init(None)
    from kagami_receiver.airplay import AUDIO_PLUGINS, MEDIA_PLUGINS, capabilities
    from kagami_receiver.smartview import MEDIA_PLUGINS as SMART_PLUGINS
    missing = [name for name in set(AUDIO_PLUGINS + MEDIA_PLUGINS + SMART_PLUGINS +
               ('appsrc', 'appsink', 'videoconvert', 'videocrop', 'videoflip', 'videoscale', 'videorate', 'v4l2sink'))
               if not Gst.ElementFactory.find(name)]
    if missing:
        raise SystemExit('Missing bundled media plugins: ' + ', '.join(sorted(missing)))
    capabilities()
    if sys.argv[1:2] == ['--appimage-gtk-check']:
        Gtk.init()
        window = Gtk.Window(title='Kagami packaged GTK smoke')
        header = Gtk.HeaderBar()
        window.set_titlebar(header)
        window.set_child(Gtk.Label(label='Kagami'))
        window.present()
        from gi.repository import GLib
        context = GLib.MainContext.default()
        for _ in range(20):
            while context.pending():
                context.iteration(False)
        assert window.get_visible()
        window.destroy()
    print(f'Kagami AppImage: Python {sys.version.split()[0]}, GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}, {Gst.version_string()}; runtime/plugins/backend ready')
else:
    from kagami_receiver.__main__ import main
    raise SystemExit(main())
