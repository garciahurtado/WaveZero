# SPDX-FileCopyrightText: 2018 Kattni Rembor for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""CircuitPython Essentials Audio Out WAV example"""
import time
import board
import digitalio
from audiocore import WaveFile
from audiopwmio import PWMAudioOut as AudioOut


def main():
    wave_file = open("sound/warchief-guitar.wav", "rb")
    wave = WaveFile(wave_file)
    audio = AudioOut(board.GP13)
    print("Playing sound file...")

    while audio.playing:
        audio.play(wave)

    print("Done!")
