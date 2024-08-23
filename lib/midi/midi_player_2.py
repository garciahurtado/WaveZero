# midi_player.py

from machine import Pin
from wav.myDMA import myDMA
from wav.myPWM import myPWM
import uasyncio as asyncio
import math
import utime
import uctypes

class MIDIPlayer:
    def __init__(self, pin=Pin(18), dma_channel=8, dma_timer=3, pwm_bits=10):
        print("Initializing MIDIPlayer")
        self.pwm_bits = pwm_bits
        self.PWM_DIVIDER = 1
        self.PWM_TOP = 1023 if pwm_bits == 10 else 255
        self.PWM_HALF = self.PWM_TOP // 2

        self.pin = pin
        self.pwm = myPWM(pin, divider=self.PWM_DIVIDER, top=self.PWM_TOP)
        self.pwm.duty(self.PWM_HALF)

        # Get the address of the PWM duty register
        self.PWM_CC = self.pwm.PWM_CC
        print(f"PWM CC register address: 0x{self.PWM_CC:08X}")

        self.sample_rate = 22050  # Sample rate
        print(f"Sample rate: {self.sample_rate}")
        self.dma = myDMA(dma_channel, timer=dma_timer, clock_MUL=15, clock_DIV=42517)
        self.buffer_size = 512  # Buffer size
        self.buffer = bytearray(self.buffer_size * 2)  # 16-bit samples
        self.current_note = None
        self.phase = 0

    def sine_wave(self, frequency):
        print(f"Generating sine wave for frequency: {frequency}")
        period = int(self.sample_rate / frequency)
        amplitude = self.PWM_TOP // 2  # Full range of PWM
        for i in range(self.buffer_size):
            sample = int(amplitude * math.sin(2 * math.pi * self.phase / period) + self.PWM_HALF)
            self.buffer[i*2] = sample & 0xFF
            self.buffer[i*2 + 1] = (sample >> 8) & 0xFF
            self.phase = (self.phase + 1) % period
        print(f"First few samples: {self.buffer[:10]}")

    def note_to_freq(self, note):
        return 440 * (2 ** ((note - 69) / 12))

    async def play_note(self, note, duration_ms):
        print(f"Playing note: {note} for {duration_ms}ms")
        self.current_note = note
        frequency = self.note_to_freq(note)
        start_time = utime.ticks_ms()
        end_time = start_time + duration_ms

        while utime.ticks_diff(end_time, utime.ticks_ms()) > 0:
            self.sine_wave(frequency)
            # Set up DMA to transfer directly to PWM duty register
            self.dma.move(uctypes.addressof(self.buffer), self.PWM_CC, self.buffer_size * 2, start=True)
            while self.dma.isBusy():
                await asyncio.sleep_ms(1)

        self.current_note = None

    async def play_midi_file(self, filename):
        print("Playing test melody")
        notes = [60, 62, 64, 65, 67, 69, 71, 72]  # C4 to C5
        for note in notes:
            await self.play_note(note, 500)  # Play each note for 500 ms
        await asyncio.sleep_ms(500)  # Pause at the end

    async def stop(self):
        print("Stopping playback")
        self.dma.abort()
        self.current_note = None

def test():
    player = MIDIPlayer()

    async def main():
        await player.play_midi_file("placeholder.mid")

    asyncio.run(main())