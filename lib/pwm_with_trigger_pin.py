import uarray as array

from machine import Pin, mem32
import rp2
import math
import utime
from uctypes import addressof

# Constants

SINE_TABLE_SIZE = 256
sine_table = [int((math.sin(2 * math.pi * i / SINE_TABLE_SIZE) + 1) * 127.5) for i in range(SINE_TABLE_SIZE)]

AUDIO_RATE = 44100  # Audio sample rate
# PIO_FREQ = 340_000  # PIO frequency
PIO_FREQ = 100_000  # PIO frequency
NUM_INSTR = 4
PWM_PERIOD = PIO_FREQ / NUM_INSTR
to_micro = 1000000

DMA_BASE = 0x50000000
PIO0_BASE = 0x50200000
PIO0_TXF0 = PIO0_BASE + 0x10

BUFFER_SIZE = 256

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32)
def audio_pwm():
    pull()              # Pull 32-bit value from FIFO
    mov(x, osr)         # Move value to X register
    mov(y, 65535)       # Set up counter (16-bit resolution)

    label("loop")
    jmp(x_not_y, "skip")
    set(pins, 0)        # Set pin high if X >= Y
    jmp("continue")

    label("skip")
    set(pins, 1)        # Set pin low if X < Y
    label("continue")
    jmp(y_dec, "loop")  # Decrement Y and loop

class AudioPWM:
    def __init__(self, pin_number):
        self.all_buffers = create_waveform_buffers()

        self.pin = Pin(pin_number, Pin.OUT)
        self.sm = rp2.StateMachine(0, audio_pwm, freq=PIO_FREQ, set_base=self.pin)
        self.sm.active(1)
        self.set_duty(128)  # 50% duty cycle

        # Setup DMA
        initial_frequencies = [440, 440, 440, 440]  # A4 for all waves
        self.setup_all_dma(self.all_buffers, initial_frequencies)


    def set_duty(self, duty):
        self.sm.put(duty)

    def setup_dma_channel(self, channel, buffer_address, buffer_size, phase_increment):
        CH_READ_ADDR = DMA_BASE + channel * 0x40
        CH_WRITE_ADDR = CH_READ_ADDR + 0x4
        CH_TRANS_COUNT = CH_READ_ADDR + 0x8
        CH_CTRL_TRIG = CH_READ_ADDR + 0xC
        CH_AL1_CTRL = CH_READ_ADDR + 0x10
        CH_AL1_READ_ADDR = CH_READ_ADDR + 0x14
        CH_AL1_WRITE_ADDR = CH_READ_ADDR + 0x18
        CH_AL2_CTRL = CH_READ_ADDR + 0x1C
        CH_AL2_TRANS_COUNT = CH_READ_ADDR + 0x20
        CH_AL3_CTRL = CH_READ_ADDR + 0x24
        CH_AL3_WRITE_ADDR = CH_READ_ADDR + 0x28

        mem32[CH_READ_ADDR] = buffer_address
        mem32[CH_WRITE_ADDR] = PIO0_TXF0
        mem32[CH_TRANS_COUNT] = 1

        # Configure main control register
        ctrl = 0x3b000000 | (channel << 11)  # Chain to next channel, no IRQ, 8-bit transfers
        mem32[CH_CTRL_TRIG] = ctrl

        # Configure AL1 (Read Address)
        mem32[CH_AL1_CTRL] = 0x40000000  # Enable
        mem32[CH_AL1_READ_ADDR] = phase_increment

        # Configure AL2 (Transfer Count)
        mem32[CH_AL2_CTRL] = 0xC0000000  # Enable, wrap
        mem32[CH_AL2_TRANS_COUNT] = buffer_size - 1

        # Configure AL3 (Write Address)
        mem32[CH_AL3_CTRL] = 0x80000000  # Enable
        mem32[CH_AL3_WRITE_ADDR] = PIO0_TXF0

    def calculate_phase_increment(self, frequency, buffer_size, pio_freq):
        return int((frequency * buffer_size * (1 << 32)) / pio_freq)

    def change_frequency(self, channel, new_frequency):
        CH_AL1_READ_ADDR = DMA_BASE + channel * 0x40 + 0x14
        buffer_size = len(self.all_buffers[channel])
        phase_increment = self.calculate_phase_increment(new_frequency, buffer_size, PIO_FREQ)
        mem32[CH_AL1_READ_ADDR] = phase_increment

    def setup_all_dma(self, buffers, frequencies):
        for i, (buffer, freq) in enumerate(zip(buffers, frequencies)):
            phase_increment = self.calculate_phase_increment(freq, len(buffer), 125_000_000)
            self.setup_dma_channel(i, addressof(buffer), len(buffer), phase_increment)

    def play_tone(self, frequency, duration):
        start_time = utime.ticks_us()
        phase_accumulator = 0
        phase_increment = int(frequency * SINE_TABLE_SIZE * 65536 / AUDIO_RATE)

        while utime.ticks_diff(utime.ticks_us(), start_time) < duration * 1000000:
            index = (phase_accumulator >> 16) & (SINE_TABLE_SIZE - 1)
            duty = sine_table[index]
            self.set_duty(duty)

            phase_accumulator += phase_increment
            utime.sleep_us(int(1000000 / AUDIO_RATE))

    def stop(self):
        self.sm.active(0)
        self.pin.value(0)



""" Waveform buffers """


def create_waveform_buffers():
    sine_buffer = create_sine_buffer()
    square_buffer = create_square_buffer()
    triangle_buffer = create_triangle_buffer()
    sawtooth_buffer = create_sawtooth_buffer()

    all_buffers = [sine_buffer, square_buffer, triangle_buffer, sawtooth_buffer]
    return all_buffers

def create_sine_buffer():
    return array.array('I', [int((math.sin(2 * math.pi * i / BUFFER_SIZE) + 1) * 127.5) for i in range(BUFFER_SIZE)])

def create_square_buffer():
    return array.array('I', [255 if i < BUFFER_SIZE // 2 else 0 for i in range(BUFFER_SIZE)])

def create_triangle_buffer():
    return array.array('I', [int(255 * (2 * abs(i / BUFFER_SIZE - 0.5))) for i in range(BUFFER_SIZE)])

def create_sawtooth_buffer():
    return array.array('I', [int(255 * (i / BUFFER_SIZE)) for i in range(BUFFER_SIZE)])


try:
    print("Starting audio PWM test. Listen for tones.")
    audio_pwm = AudioPWM(18)  # Use GPIO 18 for audio output

    frequencies = [440, 294, 330, 349, 392, 440, 494, 523]  # A4 to C5
    for freq in frequencies:
        print(f"Playing {freq} Hz")
        audio_pwm.change_frequency(0, freq)  # Change frequency of first channel
        utime.sleep(0.5)  # Play each tone for 0.5 seconds


    while True:
        # Cycle through different duty cycles
        for duty in [0, 64, 128, 192, 255]:
            print(f"Setting duty cycle to {duty}")
            audio_pwm.set_duty(duty)
            utime.sleep(1)
except KeyboardInterrupt:
    print("Test interrupted.")
finally:
    audio_pwm.stop()
    print("Audio PWM stopped.")