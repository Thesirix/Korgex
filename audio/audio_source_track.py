from array import array

from audiostream_compat import ThreadSource


class AudioSourceTrack(ThreadSource):
    steps = ()
    step_nb_samples = 0

    def __init__(self, output_stream, wav_samples, bpm, sample_rate, min_bpm, *args, **kwargs):
        ThreadSource.__init__(self, output_stream, *args, **kwargs)
        self.current_sample_index = 0
        self.current_step_index = 0
        self.wav_samples = wav_samples
        self.nb_wav_samples = len(wav_samples)
        self.min_bpm = min_bpm
        self.bpm = bpm
        self.sample_rate = sample_rate
        self.last_sound_sample_start_index = 0
        self.step_nb_samples = self.compute_step_nb_samples(bpm)
        self.buffer_nb_samples = self.compute_step_nb_samples(min_bpm)
        self.silence = array('h', b"\x00\x00" * self.buffer_nb_samples)

        if self.bpm != 0:
            n = int(self.sample_rate * 15 / self.bpm)
            if n != self.step_nb_samples:
                self.step_nb_samples = n

        self.step_pitch_samples = {}
        self.piano_roll_notes = {}

    def set_piano_roll_notes(self, notes, original_samples):
        from piano_roll import pitch_shift, ORIGINAL_MIDI
        self.piano_roll_notes = dict(notes)
        semitone_cache = {}
        new_step_samples = {}
        for (step, midi) in notes:
            semitones = midi - ORIGINAL_MIDI
            if semitones not in semitone_cache:
                semitone_cache[semitones] = pitch_shift(original_samples, semitones)
            new_step_samples[step] = semitone_cache[semitones]
        self.step_pitch_samples = new_step_samples

    def set_steps(self, steps):
        if len(steps) != len(self.steps):
            self.current_step_index = 0
        self.steps = steps

    def set_bpm(self, bpm):
        self.bpm = bpm
        self.step_nb_samples = self.compute_step_nb_samples(bpm)

    def compute_step_nb_samples(self, bpm_value):
        if bpm_value != 0:
            n = int(self.sample_rate * 15 / bpm_value)
            return n
        return 0

    def no_steps_activated(self):
        if self.step_pitch_samples:
            return False
        if len(self.steps) == 0:
            return True
        for i in range(len(self.steps)):
            if self.steps[i] == 1:
                return False
        return True

    def _piano_roll_buf(self, samples, step_nb):
        nb = len(samples)
        if nb >= step_nb:
            return array('h', samples[0:step_nb])
        buf = array('h', samples[0:nb])
        buf.extend(self.silence[0:step_nb - nb])
        return buf

    def _attack_buf(self, step_nb):
        if self.nb_wav_samples >= step_nb:
            return self.wav_samples[0:step_nb]
        silence_nb = step_nb - self.nb_wav_samples
        buf = array('h', self.wav_samples[0:self.nb_wav_samples])
        buf.extend(self.silence[0:silence_nb])
        return buf

    def _sustain_buf(self, step_nb):
        index = self.current_sample_index - self.last_sound_sample_start_index
        if index > self.nb_wav_samples:
            return self.silence[0:step_nb]
        if self.nb_wav_samples - index >= step_nb:
            return self.wav_samples[index:step_nb + index]
        silence_nb = step_nb - self.nb_wav_samples + index
        buf = array('h', self.wav_samples[index:self.nb_wav_samples])
        buf.extend(self.silence[0:silence_nb])
        return buf

    def get_bytes_array(self):
        step = self.current_step_index
        step_nb = self.step_nb_samples

        if step in self.step_pitch_samples:
            result_buf = self._piano_roll_buf(self.step_pitch_samples[step], step_nb)
            self.last_sound_sample_start_index = self.current_sample_index
        elif self.no_steps_activated():
            result_buf = self.silence[0:step_nb]
        elif self.steps[step] == 1:
            self.last_sound_sample_start_index = self.current_sample_index
            result_buf = self._attack_buf(step_nb)
        else:
            result_buf = self._sustain_buf(step_nb)

        self.current_sample_index += step_nb
        self.current_step_index += 1
        if self.current_step_index >= len(self.steps):
            self.current_step_index = 0

        if result_buf is None:
            print("result_buf is None")
            return self.silence[0:step_nb]
        if len(result_buf) != step_nb:
            print("result_buf len is not step_nb_samples")

        return result_buf

    def get_bytes(self):
        return self.get_bytes_array().tobytes()
