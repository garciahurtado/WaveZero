import gc
import sys

import micropython
import random
import utime as time

import utime

from midi.adsr_envelope import Voice, ADSREnvelope
from midi.midi_player import MidiPlayer
from midi.config import SAMPLE_RATE
from midi.sound_effects import Delay
from midi.synth import Synthesizer

# Hardware setup:
# - GP0 connected to 1kΩ resistor
# - 10µF capacitor from resistor to ground
# - LM386 amplifier connected as described
# - 1W speaker connected to LM386 output

pwm0 = None

hungarian_minor_scale = [
    440.00,  # A4
    466.16,  # B♭4
    528.01,  # C#
    586.67,  # D5
    660.00,  # E5
    693.24,  # F5
    830.61,  # G#5
    880.00  # A5
]

def run():
    global pwm0
    global hungarian_minor_scale
    print("Testing MIDI")

    player = MidiPlayer()


    # synth = Synthesizer(max_voices=4)
    #
    # # Play a chord with effects
    # frequencies = [262, 330, 392]  # C4, E4, G4
    # for freq in frequencies:
    #     synth.add_voice(freq)

    # melody = get_melody()
    # print(f"- Playing voices @ {SAMPLE_RATE}")
    # for note, dur in melody:
    #     note = note * SAMPLE_RATE
    #     player.play_tone(note, 10) # ms
    #
    #     time.sleep(1)

    print("... playback finished ...")
    #
    # for freq in frequencies:
    #     synth.remove_voice(freq)
    # synth.cleanup()


    # player.play_melody(get_melody())
    finish(player)

    # Play a simple melody
    # notes = [262, 294, 330, 349, 392, 440, 494, 523]  # C4 to C5

    for note in hungarian_minor_scale:
        player.play_tone(int(note), 300)
        utime.sleep_ms(50)

    # Play a chord
    # player.play_tone(262, 500)  # C4
    # utime.sleep_ms(50)
    # player.play_tone(330, 500)  # E4
    # utime.sleep_ms(50)
    # player.play_tone(392, 500)  # G4


    # Cleanup

    # Optionally, you can reset the pin to its default state

    print("Finished")

def finish(player):
    player.stop()
    sys.exit()

def play_random(player):
    global hungarian_minor_scale
    durations = [450, 300, 150]
    cur_duration = durations[0]
    note = hungarian_minor_scale[0]

    for id in range(12):
        # Dont always change the note
        pct = 50
        if random.random() < pct / 100:
            note = random.choice(hungarian_minor_scale)

        # Dont always change the duration
        pct = 20
        if random.random() < pct / 100:
            cur_duration = random.choice(durations)

        player.play_tone(int(note), cur_duration)
        utime.sleep_ms(50)

def get_melody():
    melody = [
        (440.00, 1000),
        (554.37, 250),
        (659.25, 250),
        (830.61, 500),
        (698.46, 250),
        (587.33, 250),
        (466.16, 500),
        (554.37, 250),
        (440.00, 750),
        (659.25, 500),
        (830.61, 250),
        (880.00, 250),
        (698.46, 500),
        (587.33, 250),
        (466.16, 250),
        (440.00, 500),
        (554.37, 250),
        (659.25, 250),
        (587.33, 500),
        (466.16, 250),
        (554.37, 250),
        (440.00, 1000),


        # Mysterious bridge (quieter, longer notes, focus on unusual intervals)
        (466.16, 1000), # Bb4 (long, eerie start)
        (554.37, 750),  # C#5
        (493.88, 750),  # B4 (out of scale, adds tension)
        (466.16, 500),  # Bb4
        (415.30, 1000), # Ab4 (out of scale, very tense)
        (440.00, 750),  # A4
        (554.37, 750),  # C#5
        (523.25, 1000), # C5 (out of scale, unresolved tension)
        #
        # # Apocalyptic chorus (louder, faster, more dramatic)
        # (880.00, 25),  # A5 (high, intense start)
        # (830.61, 25),  # G#5
        # (698.46, 25),  # F5
        # (880.00, 25),  # A5
        # (1108.73, 100), # C#6 (peak of intensity)
        # (1046.50, 25), # C6 (out of scale, harsh)
        # (880.00, 25),  # A5
        # (932.33, 100),  # Bb5 (dissonant with previous note)
        # (880.00, 25),  # A5
        # (739.99, 25),  # F#5 (out of scale, adds to chaos)
        # (698.46, 25),  # F5
        # (659.25, 25),  # E5
        # (622.25, 100),  # Eb5 (out of scale, unsettling)
        # (587.33, 25),  # D5
        # (554.37, 25),  # C#5
        # (466.16, 25),  # Bb4
        # (440.00, 1000)  # A4 (final resolution)
    ]
    return melody

def debug_synth():
    # TEST
    player = MidiPlayer()
    player.play_tone(262, 500)  # C4

    synth = Synthesizer(max_voices=4)

    # Add voices (C4, E4, G4)
    frequencies = [262, 330, 392]
    # for freq in frequencies:
    #     synth.add_voice(freq)
    synth.add_voice(440)

    print(f"<Playing 4 voices @ {SAMPLE_RATE} Hz>")

    # Play for 5 seconds
    start_time = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start_time) < 5000:
        sample = synth.get_sample()
        player.play_sample(sample)
        # player.play_melody(get_melody())


# came from main.py
def midi_test():
    pwm_player = None
    player = pwm_player.audio_pwmSimplePwmPlayer(Pin(18))

    print("Play 440")
    player.play(440, 2)

    print("Play 220")
    player.play(220, 2)

    print("Play 880")
    player.play(880, 2)

    print("Play 440")
    player.play(440, 0.5)
    sleep(5)
    player.stop()

    sys.exit(1)

