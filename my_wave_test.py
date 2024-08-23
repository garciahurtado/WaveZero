import array
import math
import random

import micropython
import uctypes
from wav.myDMA import myDMA
from wav.myPWM import myPWM
from machine import Pin
import uasyncio as asyncio

'''
Registers:

r0: buffer address
r1: number of word to do
r2: 8 or 10 bit PWM, then r2 hold data reference by r0
r3: 32768 to convert (-32768..32767) to (0..65535)
r4: hold 255 or 1023 (8 or 10 bits)
r5:  hold /64  or /256 ( 6 or 8 bit shift)
'''

@micropython.asm_thumb
def convert_to_pwm(r0,r1,r2):
    #r3=32768
    mov(r3,1)
    mov(r4,15)
    lsl(r3,r4)
    # 8bits or 10 bit PWM
    mov(r4,255)
    cmp(r2,10)
    bne(PWM8BITS)
    #ok we are 10 bits
    # set r4 for 1023
    lsl(r4,r4,2)
    add(r4,r4,3)
    mov(r5,6)
    b(loop)
    label(PWM8BITS)
    #ok then this is 8 bits
    #r4 already to 255
    mov(r5,8)
    label(loop)
    # get 16 bit data
    ldrh(r2,[r0,0])
    # add 32768
    add(r2,r2,r3)
    # shift right 6 bit or 8 bit
    lsr(r2,r5)
    # and 255 or 1023
    and_(r2,r4)
    # store new data
    strh(r2,[r0,0])
    add(r0,2)
    sub(r1,1)
    bgt(loop)

class MidiPlayer:
    def __init__(self, pin=18,
                 dma_channel_1=0, dma_channel_2=1, dma_timer=3, pwm_bits=10, sample_rate=44100):
        """
        Initialize the WavePlayer with PWM and DMA settings.

        :param left_pin: Pin for left audio channel
        :param right_pin: Pin for right audio channel
        :param virtual_gnd_pin: Pin for virtual ground (can be None)
        :param dma_channel_1: First DMA channel number
        :param dma_channel_2: Second DMA channel number
        :param dma_timer: DMA timer number
        :param pwm_bits: PWM resolution (8 or 10 bits)
        """
        self.sample_rate = sample_rate
        self.out_pin = Pin(pin)
        self.setup_pwm(self.out_pin, pwm_bits)

        print(f"Setting up DMA channels {dma_channel_1} and {dma_channel_2}")
        self.setup_dma(dma_channel_1, dma_channel_2, dma_timer, sample_rate)

        """
        Calculate frame and data sizes
        """
        self.frame_size = 1024
        self.data_size = self.frame_size * 2

        # Mock MIDI data
        self.mock_midi_data = self.generate_mock_midi_data()
        self.current_frame = 0

    def setup_pwm(self, out_pin, pwm_bits):
        """
        Set up PWM for audio output.

        :param out_pin: Pin for audio channel
        :param pwm_bits: PWM resolution (8 or 10 bits)
        """
        self.pwm_bits = pwm_bits
        self.pwm_divider = 1
        self.pwm_max = 1023 if pwm_bits == 10 else 255
        self.pwm_mid = self.pwm_max // 2

        # Initialize PWM for left and right channels
        self.pwm_ch = myPWM(out_pin, divider=self.pwm_divider, top=self.pwm_max)
        self.pwm_ch.duty(self.pwm_mid)

        print(f"PWM set up on pin {out_pin} with {pwm_bits} bits resolution")
        print(f"PWM max: {self.pwm_max}, PWM mid: {self.pwm_mid}")


    def setup_dma(self, dma_channel_1, dma_channel_2, dma_timer, sample_rate):
        """
        Set up DMA channels for audio transfer.

        :param dma_channel_1: First DMA channel number
        :param dma_channel_2: Second DMA channel number
        :param dma_timer: DMA timer number
        :param sample_rate: Audio sample rate in Hz

        """
        self.dma_channel_1 = dma_channel_1
        self.dma_channel_2 = dma_channel_2
        self.dma_timer = dma_timer

        """
        Configure DMA channels based on the audio sample rate.
        """
        # Special configuration for 44.1 kHz sample rate
        if sample_rate == 44100:
            self.dma_1 = myDMA(self.dma_channel_1, timer=self.dma_timer, clock_MUL=15, clock_DIV=42517)
        else:
            # General configuration for other sample rates
            self.dma_1 = myDMA(self.dma_channel_1, timer=self.dma_timer, clock_MUL=sample_rate // 2000,
                               clock_DIV=62500)

        self.dma_2 = myDMA(self.dma_channel_2, timer=self.dma_timer)

        # Set up DMA control for both channels
        print("Setting DMA control")

        self.dma_1.setCtrl(src_inc=True, dst_inc=False, data_size=4, chainTo=self.dma_2.channel)
        self.dma_2.setCtrl(src_inc=True, dst_inc=False, data_size=4, chainTo=self.dma_1.channel)

        print("DMA setup complete")

    def generate_mock_midi_data(self):
        # Generate a simple repeating pattern of MIDI-like data
        pattern = []
        for _ in range(16):
            note = random.randint(60, 72)  # MIDI notes C4 to C5
            velocity = random.randint(64, 127)  # Medium to full velocity
            pattern.extend([note, velocity, 0, 0])  # Each MIDI event is 4 bytes
        return pattern * (self.frame_size // 16)  # Repeat pattern to fill frame

    def process_audio_frame(self):
        """
        Read and process a single audio frame from the wave file.

        :return: Processed audio data
        """

        # Instead of reading from a file, we'll use our mock MIDI data
        start = self.current_frame * self.frame_size
        end = start + self.frame_size
        audio_data = bytes(self.mock_midi_data[start:end])

        # Convert the mock MIDI data to PWM values
        convert_to_pwm(uctypes.addressof(audio_data), len(audio_data) // 2, self.pwm_bits)

        # Move to the next frame, wrapping around if we reach the end
        self.current_frame = (self.current_frame + 1) % (len(self.mock_midi_data) // self.frame_size)

        return audio_data

    def play(self):
        while True:
            audio_data = self.process_audio_frame()
            self.transfer_dma(self.dma_1, audio_data, self.frame_size)
            # You might want to add a small delay here to control playback speed
            # await asyncio.sleep_ms(50)

    def stop(self):
        """
        Stop DMA transfers and audio playback.
        """
        self.dma_1.abort()
        self.dma_2.abort()

    def transfer_dma(self, dma_channel, audio_data, frame_size):
        """
        Perform DMA transfer for audio data.

        :param dma_channel: DMA channel to use
        :param audio_data: Audio data to transfer
        :param frame_size: Number of frames in the audio data
        """
        print("Starting DMA transfer")

        dma_channel.move(uctypes.addressof(audio_data), self.pwm_ch.PWM_CC, frame_size * 4)
        while dma_channel.isBusy():
            pass
            # await asyncio.sleep(0)

        print("DMA transfer complete")

    def generate_debug_tone(self):
        # Generate a simple sine wave
        frequency = 440  # A4 note
        samples = array.array('h', [0] * self.frame_size)
        for i in range(self.frame_size):
            samples[i] = int(32767 * math.sin(2 * math.pi * frequency * i / self.sample_rate))
        return samples

    def process_debug_frame(self):
        if not hasattr(self, 'debug_tone'):
            self.debug_tone = self.generate_debug_tone()

        audio_data = bytes(self.debug_tone)
        convert_to_pwm(uctypes.addressof(audio_data), len(audio_data) // 2, self.pwm_bits)
        return audio_data

    def play_debug_tone(self):
        print("CRAP")
        while True:
            audio_data = self.process_debug_frame()
            print("Just before transfer DMA")
            self.transfer_dma(self.dma_1, audio_data, self.frame_size)


