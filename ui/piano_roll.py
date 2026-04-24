import numpy as np
from array import array

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, Line
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

MIDI_MIN = 36
MIDI_MAX = 84
NB_PITCHES = MIDI_MAX - MIDI_MIN   # 48
ORIGINAL_MIDI = 60                  # C4 — assumed recording pitch

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
BLACK_KEYS = {1, 3, 6, 8, 10}

CELL_H = dp(13)
CELL_W = dp(28)
KEY_W = dp(48)
GRID_H = NB_PITCHES * CELL_H

# Pre-render octave labels once at import time so they never block the audio thread
_OCTAVE_TEXTURES = {}


def _build_octave_textures():
    for midi in range(MIDI_MIN, MIDI_MAX):
        if midi % 12 == 0:
            name = NOTE_NAMES[midi % 12] + str(midi // 12 - 1)
            lbl = CoreLabel(text=name, font_size=dp(8))
            lbl.refresh()
            _OCTAVE_TEXTURES[midi] = lbl.texture


# Build immediately on import (main thread, before any popup opens)
_build_octave_textures()


def is_black(midi):
    return (midi % 12) in BLACK_KEYS


def midi_name(midi):
    return NOTE_NAMES[midi % 12] + str(midi // 12 - 1)


def pitch_shift(samples, semitones):
    if semitones == 0:
        return samples
    ratio = 2.0 ** (semitones / 12.0)
    src = np.array(samples, dtype=np.float32)
    n = len(src)
    new_n = max(1, int(round(n / ratio)))
    out = np.interp(np.linspace(0, n - 1, new_n), np.arange(n), src)
    return array('h', np.clip(out, -32768, 32767).astype(np.int16).tolist())


class PianoKeysWidget(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.width = KEY_W
        self.height = GRID_H
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._draw, 0)

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            for row in range(NB_PITCHES):
                midi = MIDI_MAX - 1 - row
                y = self.y + (NB_PITCHES - 1 - row) * CELL_H
                if is_black(midi):
                    Color(0.1, 0.1, 0.1, 1)
                    Rectangle(pos=(self.x, y + 1), size=(KEY_W * 0.68, CELL_H - 2))
                else:
                    Color(0.88, 0.88, 0.88, 1)
                    Rectangle(pos=(self.x, y + 1), size=(KEY_W - 2, CELL_H - 2))
                    if midi in _OCTAVE_TEXTURES:
                        tex = _OCTAVE_TEXTURES[midi]
                        Color(0.25, 0.25, 0.25, 1)
                        Rectangle(
                            texture=tex,
                            pos=(self.x + KEY_W - tex.width - dp(4),
                                 y + (CELL_H - tex.height) / 2),
                            size=tex.size,
                        )


class NoteGridWidget(Widget):
    def __init__(self, nb_steps, on_notes_changed=None, **kwargs):
        super().__init__(**kwargs)
        self.nb_steps = nb_steps
        self.on_notes_changed = on_notes_changed
        self.notes = {}
        self.size_hint = (None, None)
        self.width = nb_steps * CELL_W
        self.height = GRID_H
        self.bind(pos=self._draw, size=self._draw)
        Clock.schedule_once(self._draw, 0)

    def _draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            # Row backgrounds
            for row in range(NB_PITCHES):
                midi = MIDI_MAX - 1 - row
                y = self.y + (NB_PITCHES - 1 - row) * CELL_H
                Color(0.13, 0.13, 0.16, 1) if is_black(midi) else Color(0.20, 0.20, 0.24, 1)
                Rectangle(pos=(self.x, y), size=(self.width, CELL_H))

            # Vertical step lines
            for col in range(self.nb_steps + 1):
                x = self.x + col * CELL_W
                if col % 4 == 0:
                    Color(0.55, 0.55, 0.60, 1)
                    Line(points=[x, self.y, x, self.top], width=1.2)
                else:
                    Color(0.28, 0.28, 0.33, 1)
                    Line(points=[x, self.y, x, self.top], width=1)

            # Horizontal pitch lines
            for row in range(NB_PITCHES + 1):
                y = self.y + row * CELL_H
                if (MIDI_MAX - row) % 12 == 0:
                    Color(0.45, 0.45, 0.50, 1)
                else:
                    Color(0.25, 0.25, 0.29, 1)
                Line(points=[self.x, y, self.right, y], width=1)

            # Notes
            for (step, midi) in self.notes:
                row = MIDI_MAX - 1 - midi
                x = self.x + step * CELL_W
                y = self.y + (NB_PITCHES - 1 - row) * CELL_H
                Color(0.15, 0.85, 0.45, 1)
                Rectangle(pos=(x + 2, y + 2), size=(CELL_W - 4, CELL_H - 4))

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        step = int((touch.x - self.x) / CELL_W)
        row = int((self.top - touch.y) / CELL_H)
        if 0 <= step < self.nb_steps and 0 <= row < NB_PITCHES:
            midi = MIDI_MAX - 1 - row
            key = (step, midi)
            if key in self.notes:
                del self.notes[key]
            else:
                self.notes[key] = True
            self._draw()
            if self.on_notes_changed:
                self.on_notes_changed(dict(self.notes))
        return True


class PianoRollPopup(ModalView):
    def __init__(self, sound_name, nb_steps, track_source, original_samples, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (0.96, 0.88)
        self.background_color = (0.07, 0.07, 0.09, 1)
        self.overlay_color = (0, 0, 0, 0.7)
        self.track_source = track_source
        self.original_samples = original_samples

        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))
        self.add_widget(root)

        # Header
        header = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        root.add_widget(header)

        title = Label(
            text=f'PIANO ROLL  ·  {sound_name}',
            font_size=dp(13),
            bold=True,
            color=(0.18, 0.85, 0.48, 1),
            halign='left',
            valign='middle',
        )
        title.bind(size=title.setter('text_size'))
        header.add_widget(title)

        clear_btn = Button(
            text='CLEAR',
            size_hint=(None, None),
            size=(dp(70), dp(30)),
            background_normal='',
            background_color=(0.25, 0.25, 0.3, 1),
            color=(0.8, 0.8, 0.85, 1),
            font_size=dp(11),
        )
        clear_btn.bind(on_press=self._on_clear)
        header.add_widget(clear_btn)

        close_btn = Button(
            text='CLOSE',
            size_hint=(None, None),
            size=(dp(70), dp(30)),
            background_normal='',
            background_color=(0.65, 0.15, 0.15, 1),
            color=(1, 1, 1, 1),
            font_size=dp(11),
        )
        close_btn.bind(on_press=self.dismiss)
        header.add_widget(close_btn)

        # Step number header
        step_header = BoxLayout(size_hint_y=None, height=dp(16), spacing=0)
        root.add_widget(step_header)
        step_header.add_widget(Widget(size_hint_x=None, width=KEY_W + dp(8)))
        for i in range(nb_steps):
            step_header.add_widget(Label(
                text=str(i + 1),
                font_size=dp(8),
                color=(0.5, 0.5, 0.55, 1) if i % 4 != 0 else (0.8, 0.8, 0.85, 1),
                size_hint_x=None,
                width=CELL_W,
            ))

        # Piano roll grid
        self.note_grid = NoteGridWidget(
            nb_steps=nb_steps,
            on_notes_changed=self._on_notes_changed,
        )
        if hasattr(track_source, 'piano_roll_notes'):
            self.note_grid.notes = dict(track_source.piano_roll_notes)

        piano_keys = PianoKeysWidget()

        self._scroll = ScrollView(do_scroll_x=False, do_scroll_y=True)
        content_box = BoxLayout(
            size_hint=(None, None),
            width=KEY_W + nb_steps * CELL_W,
            height=GRID_H,
        )
        content_box.add_widget(piano_keys)
        content_box.add_widget(self.note_grid)
        self._scroll.add_widget(content_box)

        content_row = BoxLayout(spacing=dp(8))
        content_row.add_widget(Widget(size_hint_x=None, width=dp(8)))
        content_row.add_widget(self._scroll)
        root.add_widget(content_row)

        # After layout stabilises: scroll to C4 and force a full redraw
        Clock.schedule_once(self._after_open, 0.05)

    def _after_open(self, dt):
        # Scroll to show C4 in the middle of the viewport
        c4_row = MIDI_MAX - 1 - ORIGINAL_MIDI          # row index from top
        y_bottom = (NB_PITCHES - 1 - c4_row) * CELL_H  # y from bottom of grid
        view_h = self._scroll.height
        total_h = GRID_H
        if total_h > view_h:
            target = (y_bottom - view_h / 2) / (total_h - view_h)
            self._scroll.scroll_y = max(0.0, min(1.0, target))
        # Force a redraw now that layout and scroll are settled
        self.note_grid._draw()

    def _on_notes_changed(self, notes):
        if self.track_source is not None:
            self.track_source.set_piano_roll_notes(notes, self.original_samples)

    def _on_clear(self, *_):
        self.note_grid.notes.clear()
        self.note_grid._draw()
        if self.track_source is not None:
            self.track_source.set_piano_roll_notes({}, self.original_samples)
