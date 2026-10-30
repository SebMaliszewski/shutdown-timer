#!/usr/bin/env python3
"""Shutdown Timer - GTK3 auto-shutdown app. Hidden flags: --dry-run, --autostart-seconds N (testing)."""
import sys, os, json, time, math, subprocess
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

APP_DIR = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(APP_DIR, 'assets', 'girl.png')
CFG_DIR = os.path.expanduser('~/.config/shutdown-timer')
CFG = os.path.join(CFG_DIR, 'settings.json')
MIN_M, MAX_M = 1, 1440
DEFAULTS = {'minutes': 60, 'overlay': True, 'color': '#7fd4ff', 'size': 36, 'x': 100, 'y': 100}
DRY = '--dry-run' in sys.argv

def clamp(v): return max(MIN_M, min(MAX_M, int(v)))
def fmt(sec):
    sec = max(0, int(math.ceil(sec))); h, r = divmod(sec, 3600); m, s = divmod(r, 60)
    return f'{h:02d}:{m:02d}:{s:02d}'
def parse_minutes(text, fallback=60):
    try: return clamp(float(text.strip()))
    except Exception: return clamp(fallback)

def load_cfg():
    d = dict(DEFAULTS)
    try:
        with open(CFG) as f: d.update(json.load(f))
    except Exception: pass
    return d
def save_cfg(d):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CFG, 'w') as f: json.dump(d, f, indent=2)

def poweroff():
    if DRY:
        print('[DRY-RUN] would run: systemctl poweroff', flush=True); return
    subprocess.Popen(['systemctl', 'poweroff'])

CSS = b"""
window.main { background-image: linear-gradient(160deg, #141a2e, #1d2747 60%, #24345e); color: #e6ecff; }
window.main label { color: #e6ecff; }
.title { font-size: 22px; font-weight: 800; color: #9fd8ff; }
label.subtitle { color: #8a97c2; font-size: 11px; }
label.countdown { font-family: monospace; font-size: 46px; font-weight: 800; color: #ffffff; }
label.status { color: #9fb0e0; }
.card { background-color: rgba(255,255,255,0.06); border-radius: 14px; border: 1px solid rgba(160,200,255,0.15); padding: 12px; }
button { background-image: none; background-color: rgba(120,160,255,0.14); color: #e6ecff; border-radius: 10px;
         border: 1px solid rgba(150,190,255,0.25); padding: 8px 14px; font-weight: 700; box-shadow: none; text-shadow: none; }
button:hover { background-color: rgba(120,170,255,0.30); }
button.preset.active { background-color: #3f7cff; border-color: #7fb0ff; }
button.confirm { background-color: #2f9e6e; } button.confirm:hover { background-color: #36b87f; }
button.cancel { background-color: #b8434f; } button.cancel:hover { background-color: #d24f5c; }
entry { background-image: none; background-color: rgba(0,0,0,0.35); color: #ffffff; border-radius: 10px; border: 1px solid #4a6ab8;
        font-size: 20px; font-weight: 700; padding: 6px; caret-color: #9fd8ff; }
label.hint { color: #7e8bb5; font-size: 10px; }
"""

class Overlay(Gtk.Window):
    def __init__(self, app):
        super().__init__(type=Gtk.WindowType.TOPLEVEL, title='Shutdown Timer Overlay')
        self.app = app
        self.set_decorated(False); self.set_keep_above(True); self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True); self.stick(); self.set_accept_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        scr = self.get_screen(); vis = scr.get_rgba_visual()
        self.composited = bool(vis and scr.is_composited())
        if self.composited: self.set_visual(vis)
        self.set_app_paintable(True)
        self.label = Gtk.Label(); self.label.set_margin_start(14); self.label.set_margin_end(14)
        self.label.set_margin_top(6); self.label.set_margin_bottom(6)
        self.add(self.label)
        self.connect('draw', self.on_draw)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('button-press-event', self.on_press)
        self.connect('configure-event', self.on_conf)
        c = app.cfg; self.move(int(c['x']), int(c['y']))
        self.set_text('--:--:--')
    def on_draw(self, w, cr):
        a = self.get_allocation(); r = 12
        if not self.composited:
            cr.set_source_rgb(0.08, 0.10, 0.18); cr.paint(); return False
        cr.set_source_rgba(0, 0, 0, 0); cr.set_operator(1); cr.paint(); cr.set_operator(2)
        cr.set_source_rgba(0.06, 0.08, 0.16, 0.45)
        cr.new_sub_path()
        cr.arc(a.width-r, r, r, -math.pi/2, 0); cr.arc(a.width-r, a.height-r, r, 0, math.pi/2)
        cr.arc(r, a.height-r, r, math.pi/2, math.pi); cr.arc(r, r, r, math.pi, 1.5*math.pi)
        cr.close_path(); cr.fill()
        return False
    def set_text(self, t):
        c = self.app.cfg
        self.label.set_markup(f'<span font_family="monospace" weight="heavy" size="{int(c["size"])*1024}" '
                              f'foreground="{c["color"]}">{t}</span>')
        self.resize(1, 1)
    def on_press(self, w, e):
        if e.button == 1:
            self.begin_move_drag(e.button, int(e.x_root), int(e.y_root), e.time)
        return True
    def on_conf(self, w, e):
        if not self.get_visible(): return False
        self.app.cfg['x'], self.app.cfg['y'] = self.get_position()
        self.app.schedule_save()
        return False

class App(Gtk.Window):
    def __init__(self):
        super().__init__(title='Shutdown Timer')
        self.cfg = load_cfg(); self._save_id = None
        self.end_time = None; self.warned = False; self.tick_id = None
        self.get_style_context().add_class('main')
        prov = Gtk.CssProvider(); prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        if os.path.exists(IMG): self.set_icon_from_file(IMG)
        self.set_resizable(False); self.set_position(Gtk.WindowPosition.CENTER)
        self.connect('delete-event', self.on_close)

        root = Gtk.Box(spacing=18); root.set_border_width(18); self.add(root)
        if os.path.exists(IMG):
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(IMG, -1, 440, True)
            root.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); root.pack_start(col, True, True, 0)
        t = Gtk.Label(label='Shutdown Timer', xalign=0); t.get_style_context().add_class('title'); col.pack_start(t, False, False, 0)
        st = Gtk.Label(label='Power off your computer automatically' + ('  [DRY RUN]' if DRY else ''), xalign=0)
        st.get_style_context().add_class('subtitle'); col.pack_start(st, False, False, 0)

        cd = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2); cd.get_style_context().add_class('card')
        self.cd_label = Gtk.Label(label='00:00:00'); self.cd_label.get_style_context().add_class('countdown')
        self.status = Gtk.Label(label='Idle - no shutdown scheduled'); self.status.get_style_context().add_class('status')
        cd.pack_start(self.cd_label, False, False, 0); cd.pack_start(self.status, False, False, 0)
        col.pack_start(cd, False, False, 0)

        pr = Gtk.Box(spacing=8, homogeneous=True); self.presets = {}
        for m in (30, 60, 90, 120):
            b = Gtk.Button(label=f'{m} min'); b.get_style_context().add_class('preset')
            b.connect('clicked', lambda _b, m=m: self.set_minutes(m)); pr.pack_start(b, True, True, 0); self.presets[m] = b
        col.pack_start(pr, False, False, 0)

        cr = Gtk.Box(spacing=10)
        cr.pack_start(Gtk.Label(label='Custom (minutes):'), False, False, 0)
        self.entry = Gtk.Entry(); self.entry.set_width_chars(6); self.entry.set_alignment(0.5)
        self.entry.set_tooltip_text('Scroll the mouse wheel or hold left button and drag up/down to adjust')
        self.entry.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK |
                              Gdk.EventMask.BUTTON_MOTION_MASK | Gdk.EventMask.POINTER_MOTION_MASK)
        self.entry.connect('scroll-event', self.on_scroll)
        self.entry.connect('button-press-event', self.on_bpress)
        self.entry.connect('motion-notify-event', self.on_motion)
        self.entry.connect('button-release-event', self.on_brelease)
        self.entry.connect('changed', lambda e: self.highlight())
        self.entry.connect('activate', lambda e: self.on_confirm(None))
        self.entry.connect('focus-out-event', self.on_focus_out)
        self.drag_y = None; self.drag_base = 0; self.dragging = False
        cr.pack_start(self.entry, False, False, 0)
        col.pack_start(cr, False, False, 0)
        h = Gtk.Label(label='Wheel or click-and-drag up/down on the field to adjust (1-1440)', xalign=0)
        h.get_style_context().add_class('hint'); col.pack_start(h, False, False, 0)

        ac = Gtk.Box(spacing=10, homogeneous=True)
        self.bconf = Gtk.Button(label='Confirm'); self.bconf.get_style_context().add_class('confirm')
        self.bcanc = Gtk.Button(label='Cancel'); self.bcanc.get_style_context().add_class('cancel')
        self.bconf.connect('clicked', self.on_confirm); self.bcanc.connect('clicked', self.on_cancel)
        ac.pack_start(self.bconf, True, True, 0); ac.pack_start(self.bcanc, True, True, 0)
        col.pack_start(ac, False, False, 0)

        oc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); oc.get_style_context().add_class('card')
        self.chk = Gtk.CheckButton(label='Show on-screen overlay timer (drag to move)')
        self.chk.set_active(bool(self.cfg['overlay'])); self.chk.connect('toggled', self.on_overlay_toggle)
        oc.pack_start(self.chk, False, False, 0)
        r2 = Gtk.Box(spacing=10)
        r2.pack_start(Gtk.Label(label='Colour:'), False, False, 0)
        rgba = Gdk.RGBA(); rgba.parse(self.cfg['color'])
        self.colbtn = Gtk.ColorButton.new_with_rgba(rgba); self.colbtn.connect('color-set', self.on_color)
        r2.pack_start(self.colbtn, False, False, 0)
        r2.pack_start(Gtk.Label(label='Size:'), False, False, 0)
        self.size = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 12, 120, 1)
        self.size.set_value(self.cfg['size']); self.size.set_size_request(150, -1)
        self.size.connect('value-changed', self.on_size)
        r2.pack_start(self.size, True, True, 0)
        oc.pack_start(r2, False, False, 0)
        col.pack_start(oc, False, False, 0)

        self.overlay = Overlay(self)
        self.set_minutes(self.cfg['minutes'])
        self.update_ui()

    def get_minutes(self): return parse_minutes(self.entry.get_text(), self.cfg['minutes'])
    def set_minutes(self, m):
        m = clamp(m); self.entry.set_text(str(m)); self.cfg['minutes'] = m; self.highlight()
    def highlight(self):
        try: v = int(self.entry.get_text())
        except Exception: v = None
        for m, b in self.presets.items():
            c = b.get_style_context(); (c.add_class if m == v else c.remove_class)('active')
    def on_focus_out(self, *a): self.set_minutes(self.get_minutes()); return False
    def on_scroll(self, w, e):
        step = 5 if e.state & Gdk.ModifierType.SHIFT_MASK else 1
        d = 0
        if e.direction == Gdk.ScrollDirection.UP: d = 1
        elif e.direction == Gdk.ScrollDirection.DOWN: d = -1
        elif e.direction == Gdk.ScrollDirection.SMOOTH:
            ok, dx, dy = e.get_scroll_deltas(); d = -1 if dy > 0 else (1 if dy < 0 else 0)
        if d: self.set_minutes(self.get_minutes() + d * step)
        return True
    def on_bpress(self, w, e):
        if e.button == 1:
            self.drag_y = e.y_root; self.drag_base = self.get_minutes(); self.dragging = False
        return False
    def on_motion(self, w, e):
        if self.drag_y is None or not (e.state & Gdk.ModifierType.BUTTON1_MASK): return False
        dy = self.drag_y - e.y_root
        if not self.dragging and abs(dy) > 4: self.dragging = True
        if self.dragging:
            self.set_minutes(self.drag_base + int(dy / 4)); return True
        return False
    def on_brelease(self, w, e):
        was = self.dragging; self.drag_y = None; self.dragging = False
        return was

    def start(self, seconds):
        self.end_time = time.monotonic() + seconds; self.warned = False
        if self.tick_id: GLib.source_remove(self.tick_id)
        self.tick_id = GLib.timeout_add(250, self.tick); self.update_ui()
    def on_confirm(self, b):
        m = self.get_minutes(); self.set_minutes(m); self.save_now()
        self.start(m * 60)
        print(f'Shutdown scheduled in {m} min', flush=True)
    def on_cancel(self, b):
        if self.tick_id: GLib.source_remove(self.tick_id); self.tick_id = None
        if self.end_time: print('Shutdown cancelled', flush=True)
        self.end_time = None; self.update_ui()
    def remaining(self): return max(0, self.end_time - time.monotonic()) if self.end_time else 0
    def tick(self):
        rem = self.remaining()
        if rem <= 60 and not self.warned:
            self.warned = True
            try: subprocess.Popen(['notify-send', '-i', IMG, 'Shutdown Timer', 'The computer will shut down in 1 minute.'])
            except Exception: pass
        if rem <= 0:
            self.tick_id = None; self.end_time = None; self.update_ui(done=True); poweroff(); return False
        self.update_ui(); return True
    def update_ui(self, done=False):
        if self.end_time:
            t = fmt(self.remaining()); self.cd_label.set_text(t)
            self.status.set_text('Shutdown at ' + time.strftime('%H:%M', time.localtime(time.time() + self.remaining())))
            if self.chk.get_active():
                self.overlay.set_text(t)
                if not self.overlay.get_visible():
                    self.overlay.show_all(); self.overlay.move(int(self.cfg['x']), int(self.cfg['y']))
        else:
            self.cd_label.set_text('00:00:00')
            self.status.set_text('Shutting down...' if done else 'Idle - no shutdown scheduled')
            self.overlay.hide()
    def on_overlay_toggle(self, c):
        self.cfg['overlay'] = c.get_active(); self.save_now()
        if not c.get_active(): self.overlay.hide()
        self.update_ui()
    def overlay_refresh(self):
        self.overlay.set_text(fmt(self.remaining()) if self.end_time else '--:--:--')
    def on_color(self, b):
        r = b.get_rgba(); self.cfg['color'] = '#%02x%02x%02x' % (int(r.red*255), int(r.green*255), int(r.blue*255))
        self.save_now(); self.overlay_refresh()
    def on_size(self, s):
        self.cfg['size'] = int(s.get_value()); self.overlay_refresh(); self.schedule_save()
    def schedule_save(self):
        if self._save_id: GLib.source_remove(self._save_id)
        self._save_id = GLib.timeout_add(600, self.save_now)
    def save_now(self):
        self._save_id = None; save_cfg(self.cfg); return False
    def on_close(self, w, e):
        if self.end_time:
            d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                  buttons=Gtk.ButtonsType.NONE, text='A shutdown is scheduled.')
            d.format_secondary_text('Cancel shutdown and quit, or keep the timer running (window minimized)?')
            d.add_buttons('Keep running', 1, 'Cancel shutdown and quit', 2)
            r = d.run(); d.destroy()
            if r != 2:
                self.iconify(); return True
            self.on_cancel(None)
        self.save_now(); Gtk.main_quit(); return False

def main():
    app = App(); app.show_all()
    if '--autostart-seconds' in sys.argv:
        app.start(float(sys.argv[sys.argv.index('--autostart-seconds') + 1]))
    Gtk.main()

if __name__ == '__main__':
    main()
