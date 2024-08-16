from midi.adsr_envelope import Voice
from midi.config import SAMPLE_RATE
from midi.sound_effects import Delay, Chorus, SimpleReverb

class Synthesizer:
    def __init__(self, max_voices=4):
        self.voices = []
        self.max_voices = max_voices
        # self.delay = Delay((0.3 / 1000) * SAMPLE_RATE, 0.4)
        # self.chorus = Chorus()
        # self.reverb = SimpleReverb()
        self.sample_count = 0

    def add_voice(self, frequency, waveform='sine'):
        if len(self.voices) < self.max_voices:
            self.voices.append(Voice(frequency, waveform))
        else:
            # Replace the oldest voice if we've reached the maximum
            self.voices.pop(0)
            self.voices.append(Voice(frequency, waveform))

    def remove_voice(self, frequency):
        for voice in self.voices:
            if voice.frequency == frequency:
                voice.release()

    def get_sample(self):
        # Mix all active voices
        # sample = sum(voice.get_sample() for voice in self.voices if voice.active)
        sample = self.voices[0].get_sample()

        # Normalize
        # if self.voices:
        #     sample /= len(self.voices)

        # Apply effects
        # sample = self.delay.process(sample)
        # sample = self.chorus.process(sample)
        # sample = self.reverb.process(sample)

        self.sample_count += 1
        return sample

    def cleanup(self):
        # Remove inactive voices
        self.voices = [voice for voice in self.voices if voice.active]