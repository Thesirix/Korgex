import sys
import os

# Make audio/ and ui/ importable without package syntax
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ROOT, 'audio'))
sys.path.insert(0, os.path.join(_ROOT, 'ui'))

from kivy import Config
Config.set('graphics', 'width', '820')
Config.set('graphics', 'height', '400')
Config.set('graphics', 'minimum_width', '660')
Config.set('graphics', 'minimum_height', '320')
Config.set('graphics', 'borderless', '1')
Config.set('graphics', 'resizable', '1')

import ctypes

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import ObjectProperty, NumericProperty
from kivy.clock import Clock
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.widget import Widget

from audio_engine import AudioEngine
from sound_kit_service import SoundKitService
from track import TrackWidget

Window.clearcolor = (0.07, 0.07, 0.09, 1)

Builder.load_file('ui/track.kv')
Builder.load_file('ui/play_indicator.kv')

TRACK_NB_STEPS = 16
MIN_BPM = 80
MAX_BPM = 160


class _POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


def _cursor_screen_pos():
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


class VerticalSpacingWidget(Widget):
    pass


class DragTopBar(RelativeLayout):
    """Top bar drag using absolute screen coords to avoid window-relative feedback."""
    _drag_start = None

    def on_touch_down(self, touch):
        child_handled = super().on_touch_down(touch)
        if not child_handled and self.collide_point(*touch.pos):
            touch.grab(self)
            mx, my = _cursor_screen_pos()
            self._drag_start = (mx, my, Window.left, Window.top)
            return True
        return child_handled

    def on_touch_move(self, touch):
        if touch.grab_current is self and self._drag_start:
            mx, my = _cursor_screen_pos()
            sx, sy, wx, wy = self._drag_start
            Window.left = wx + (mx - sx)
            Window.top = wy + (my - sy)
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._drag_start = None
            return True
        return super().on_touch_up(touch)


class MainWidget(RelativeLayout):
    tracks_layout = ObjectProperty()
    play_indicator_widget = ObjectProperty()
    TRACK_STEPS_LEFT_ALIGN = NumericProperty(dp(162))
    step_index = 0
    bpm = NumericProperty(120)
    nb_tracks = NumericProperty(0)

    def __init__(self, **kwargs):
        super(MainWidget, self).__init__(**kwargs)
        self.sound_kit_service = SoundKitService()
        self.nb_tracks = self.sound_kit_service.get_nb_tracks()
        self.audio_engine = AudioEngine()
        self.mixer = self.audio_engine.create_mixer(
            self.sound_kit_service.soundkit.get_all_samples(),
            self.bpm,
            TRACK_NB_STEPS,
            self.on_mixer_current_step_changed,
            MIN_BPM,
        )

    def on_parent(self, widget, parent):
        self.play_indicator_widget.set_nb_steps(TRACK_NB_STEPS)
        for i in range(self.sound_kit_service.get_nb_tracks()):
            sound = self.sound_kit_service.get_sound_at(i)
            self.tracks_layout.add_widget(VerticalSpacingWidget())
            self.tracks_layout.add_widget(
                TrackWidget(sound, self.audio_engine, TRACK_NB_STEPS,
                            self.mixer.tracks[i], self.TRACK_STEPS_LEFT_ALIGN)
            )
        self.tracks_layout.add_widget(VerticalSpacingWidget())

    def on_mixer_current_step_changed(self, step_index):
        self.step_index = step_index
        Clock.schedule_once(self.update_play_indicator_cbk, 0)

    def update_play_indicator_cbk(self, dt):
        if self.play_indicator_widget is not None:
            self.play_indicator_widget.set_current_step_index(self.step_index)

    def on_play_button_pressed(self):
        self.mixer.audio_play()

    def on_stop_button_pressed(self):
        self.mixer.audio_stop()

    def on_close_button_pressed(self):
        os._exit(0)

    def on_bpm(self, widget, value):
        if value < MIN_BPM:
            self.bpm = MIN_BPM
            return
        if value > MAX_BPM:
            self.bpm = MAX_BPM
            return
        self.mixer.set_bpm(self.bpm)


class KorgexApp(App):
    kv_file = 'ui/korgex.kv'


KorgexApp().run()
