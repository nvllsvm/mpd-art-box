#!/usr/bin/env python
import contextlib
import pathlib
import threading
import time

import configargparse
import gi
import mpd

gi.require_version('Gtk', '3.0')

from gi.repository import GLib, Gtk, Gdk, GdkPixbuf  # noqa: E402

version = '0.0.3'


@contextlib.contextmanager
def _mpd_client(*args, **kwargs):
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            client = mpd.MPDClient()
            client.connect(*args, **kwargs)
            break
        except ConnectionRefusedError:
            if attempt == attempts:
                raise
            else:
                time.sleep(1)
    try:
        yield client
    finally:
        client.disconnect()


def _find_song_art(library, song_path):
    for path in library.joinpath(song_path).parent.iterdir():
        if path.name in ('cover.jpg', 'cover.png'):
            return path


def app_main(mpd_host, mpd_port, library):
    win = Gtk.Window(default_height=500, default_width=500)
    win.connect('destroy', Gtk.main_quit)

    win.override_background_color(
        Gtk.StateType.NORMAL, Gdk.RGBA(red=0, green=0, blue=0))

    image = Gtk.Image()
    win.add(image)
    image_path = None

    def set_image():
        nonlocal image_path

        if image_path:
            win_width, win_height = win.get_size()
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(image_path))
            aspect = (pixbuf.get_width() / pixbuf.get_height())

            if aspect < 1:
                height = win_height
                width = aspect * height
                if width > win_width:
                    height = (win_width / width) * height
                    width = win_width
            else:
                width = win_width
                height = (1 / aspect) * width
                if height > win_height:
                    width = (win_height / height) * width
                    height = win_height

            pixbuf = pixbuf.scale_simple(
                width, height, GdkPixbuf.InterpType.BILINEAR)
            image.set_from_pixbuf(pixbuf)
        else:
            image.clear()
        return False

    def mpd_loop():
        nonlocal image_path

        with _mpd_client(mpd_host, mpd_port) as client:
            while True:
                current = client.currentsong()
                if not current:
                    image_path = None
                else:
                    image_path = _find_song_art(library, current['file'])
                GLib.idle_add(set_image)
                client.idle()

    win.show_all()

    def _on_resize(*args):
        set_image()

    win.connect('size-allocate', _on_resize)

    thread = threading.Thread(target=mpd_loop)
    thread.daemon = True
    thread.start()


def main():
    parser = configargparse.ArgumentParser(
        default_config_files=['~/.config/mpd-art-box/config'])
    parser.add_argument('-c', '--config', is_config_file=True,
                        help='config path')
    parser.add_argument('--host', default='localhost',
                        help='MPD host (default: %(default)s)')
    parser.add_argument('--port', type=int, default=6600,
                        help='MPD port (default: %(default)s)')
    parser.add_argument('--library', type=pathlib.Path, required=True,
                        help='root path of the MPD library')
    parser.add_argument('--version', action='version', version=version)
    args = parser.parse_args()

    app_main(args.host, args.port, args.library.expanduser())
    Gtk.main()


if __name__ == '__main__':
    main()
