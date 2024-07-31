# SPDX-FileCopyrightText: 2018 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT
#
# DEPRECATED

"""CircuitPython Essentials Audio Out WAV example"""
from audiocore import WaveFile
from audiopwmio import PWMAudioOut as AudioOut
from machine import Pin


def main():
    wave_file = open("sound/warchief-guitar.wav", "rb")
    wave = WaveFile(wave_file)
    audio = AudioOut(Pin(13))
    print("Playing sound file...")

    while audio.playing:
        audio.play(wave)

    print("Done!")
