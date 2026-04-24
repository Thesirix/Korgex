from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.togglebutton import ToggleButton


class TrackStepButton(ToggleButton):
    pass


class TrackSoundButton(Button):
    pass


class TrackRollButton(Button):
    pass


class TrackWidget(BoxLayout):
    def __init__(self, sound, audio_engine, nb_steps, track_source, steps_left_align, **kwargs):
        super(TrackWidget, self).__init__(**kwargs)

        self.audio_engine = audio_engine
        self.sound = sound
        self.track_source = track_source
        self.nb_steps = nb_steps

        left_panel = BoxLayout(size_hint_x=None, width=steps_left_align)
        self.add_widget(left_panel)

        sound_button = TrackSoundButton()
        sound_button.text = sound.displayname
        sound_button.on_press = self.on_sound_button_press
        left_panel.add_widget(sound_button)

        roll_button = TrackRollButton()
        roll_button.text = 'ROLL'
        roll_button.size_hint_x = None
        roll_button.width = dp(38)
        roll_button.on_press = self.on_roll_button_press
        left_panel.add_widget(roll_button)

        separator_image = Image(source='images/track_separator.png')
        separator_image.size_hint_x = None
        separator_image.width = dp(15)
        left_panel.add_widget(separator_image)

        self.step_buttons = []
        for i in range(nb_steps):
            step_button = TrackStepButton()
            if int(i / 4) % 2 == 0:
                step_button.background_normal = 'images/step_normal1.png'
            else:
                step_button.background_normal = 'images/step_normal2.png'
            step_button.bind(state=self.on_step_button_state)
            self.step_buttons.append(step_button)
            self.add_widget(step_button)

    def on_sound_button_press(self):
        self.audio_engine.play_sound(self.sound.samples)

    def on_roll_button_press(self):
        from piano_roll import PianoRollPopup
        popup = PianoRollPopup(
            sound_name=self.sound.displayname,
            nb_steps=self.nb_steps,
            track_source=self.track_source,
            original_samples=self.sound.samples,
        )
        popup.open()

    def on_step_button_state(self, widget, value):
        steps = []
        for i in range(self.nb_steps):
            if self.step_buttons[i].state == 'down':
                steps.append(1)
            else:
                steps.append(0)
        self.track_source.set_steps(steps)
