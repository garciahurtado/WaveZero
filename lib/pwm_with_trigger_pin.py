import uarray as array

from machine import Pin, mem32, PWM
import rp2
import math
import utime
from uctypes import addressof

# Constants

# SINE_TABLE_SIZE = 256
# sine_table = [int((math.sin(2 * math.pi * i / SINE_TABLE_SIZE) + 1) * 127.5) for i in range(SINE_TABLE_SIZE)]

AUDIO_RATE = 44100  # Audio sample rate
# PIO_FREQ = 340_000  # PIO frequency
PIO_FREQ = 125_000_000  # PIO frequency
NUM_INSTR = 4
PWM_PERIOD = PIO_FREQ / NUM_INSTR
to_micro = 1000000

DMA_BASE = 0x50000000
PIO0_BASE = 0x50200000
PIO0_TXF0 = PIO0_BASE + 0x10

BUFFER_SIZE = 256

SINE_TABLE_SIZE = 256
sine_table = array.array('H', [int((math.sin(2 * math.pi * i / SINE_TABLE_SIZE) + 1) * 32767.5) for i in range(SINE_TABLE_SIZE)])


@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32)
def audio_pwm():
    pull()              # Pull 32-bit value from FIFO
    mov(x, osr)         # Move value to X register
    mov(y, 255)       # Set up counter (16-bit resolution)

    label("loop")
    jmp(x_not_y, "skip")
    set(pins, 1)        # Set pin high if X >= Y
    jmp("continue")

    label("skip")
    set(pins, 0)        # Set pin low if X < Y
    label("continue")
    jmp(y_dec, "loop")  # Decrement Y and loop


@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def square_wave_old():
    set(pins, 1) [31]  # High for 32 cycles
    set(pins, 0) [31]  # Low for 32 cycles

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32)
def square_wave():
    pull()
    mov(x, osr)
    set(pins, 1)
    label("delay_high")
    jmp(x_dec, "delay_high")
    set(pins, 0)
    mov(x, osr)
    label("delay_low")
    jmp(x_dec, "delay_low")

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32)
def sine_wave():
    pull()
    mov(x, osr)
    mov(y, 255)
    label("loop")
    jmp(x_not_y, "skip")
    set(pins, 1)
    jmp("continue")
    label("skip")
    set(pins, 0)
    label("continue")
    jmp(y_dec, "loop")

@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32)
def simple_wave():
    wrap_target()
    pull()
    mov(x, osr)
    set(pins, 1)
    label("delay_high")
    jmp(x_dec, "delay_high")
    nop()           # Add a small delay
    set(pins, 0)
    mov(x, osr)
    label("delay_low")
    jmp(x_dec, "delay_low")
    nop()           # Add a small delay
    wrap()


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
        print(f"Duty set to: {duty}")  # Debug print

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

        print(f"DMA Channel {channel} set up with phase increment: {phase_increment}")  # Debug print

    def calculate_phase_increment(self, frequency, buffer_size, pio_freq):
        phase_increment = int((frequency * buffer_size * (1 << 32)) / pio_freq)
        print(f"Calculated phase increment: {phase_increment} for frequency: {frequency}")  # Debug print
        return phase_increment

    def change_frequency(self, channel, new_frequency):
        CH_AL1_READ_ADDR = DMA_BASE + channel * 0x40 + 0x14
        buffer_size = len(self.all_buffers[channel])
        phase_increment = self.calculate_phase_increment(new_frequency, buffer_size, PIO_FREQ)
        mem32[CH_AL1_READ_ADDR] = phase_increment
        print(f"Changed frequency for channel {channel} to {new_frequency} Hz")  # Debug print

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
        print("AudioPWM stopped")  # Debug print


class SimpleAudioPWM:
    def __init__(self, pin_number, freq=440):
        self.pin = Pin(pin_number, Pin.OUT)
        self.sm = rp2.StateMachine(0, audio_pwm, freq=125_000_000, set_base=self.pin)
        self.sm.active(1)
        self.set_frequency(freq)

    def set_frequency(self, freq):
        period = int(125_000_000 / (freq * 256))  # 256 steps for 8-bit resolution
        self.sm.put(period)

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

# Basic Test
# ----------
# sm = rp2.StateMachine(0, square_wave, freq=10000, set_base=Pin(18))
# sm.active(1)
# exit()

# try:
#     print("Starting audio PWM test. Listen for a continuous 440 Hz tone.")
#     audio_pwm = AudioPWM(18)  # Use GPIO 18 for audio output
#     audio_pwm.change_frequency(0, 440)  # Set frequency to 440 Hz (A4)
#     while True:
#         utime.sleep(1)
# except KeyboardInterrupt:
#     print("Test interrupted.")
# finally:
#     audio_pwm.stop()
#     print("Audio PWM stopped.")



# try:
#    print("Starting simple AudioPWM test. Listen for a 440 Hz tone.")
#    audio = SimpleAudioPWM(18)  # Use GPIO 18 for audio output
#    utime.sleep(5)  # Play for 5 seconds
#    print("Changing to 880 Hz")
#    audio.set_frequency(880)
#    utime.sleep(5)  # Play for 5 more seconds
# except KeyboardInterrupt:
#    print("Test interrupted.")
# finally:
#    audio.stop()
#    print("AudioPWM stopped.")


class SineWaveGenerator:
    def __init__(self, pin_number):
        self.pin = Pin(pin_number, Pin.OUT)
        self.sm = rp2.StateMachine(0, sine_wave, freq=125_000_000, set_base=self.pin)
        self.sm.active(1)

    def set_frequency(self, freq):
        period = int(125_000_000 / (freq * SINE_TABLE_SIZE))
        for i in range(SINE_TABLE_SIZE):
            self.sm.put(sine_table[i] * period // 65535)

    def stop(self):
        self.sm.active(0)
        self.pin.value(0)

# Calculate frequency
def calculate_freq(target_freq):
    return target_freq * 64  # 64 cycles per square wave


class DebugFrequencyChangeGenerator:
    def __init__(self, pin_number):
        self.pin = Pin(pin_number, Pin.OUT)
        self.sm = rp2.StateMachine(0, simple_wave, freq=125_000_000, set_base=self.pin)
        self.sm.active(1)
        print("State Machine initialized and activated")

    def set_frequency(self, freq):
        period = int(125_000_000 / (2 * freq)) - 2  # Adjust for the two nop instructions
        print(f"Setting frequency to {freq} Hz, period: {period}")
        self.sm.active(0)  # Temporarily stop the state machine
        self.sm.restart()  # Clear the FIFO
        self.sm.put(period)
        self.sm.put(period)  # Send twice to ensure it's in the FIFO
        self.sm.active(1)  # Restart the state machine
        print("New period value sent to State Machine")

    def stop(self):
        self.sm.active(0)
        self.pin.value(0)
        print("State Machine stopped")


class SimpleSquareWaveGenerator:
    def __init__(self, pin_number):
        self.pin = Pin(pin_number, Pin.OUT)
        self.sm = rp2.StateMachine(0, square_wave, freq=125_000_000, set_base=self.pin)
        self.buffer = array.array('I', [0] * BUFFER_SIZE)
        self.dma_channel = 0
        self.setup_dma()
        self.sm.active(1)
        print("State Machine and DMA initialized and activated")

    def setup_dma(self):
        CH_READ_ADDR = DMA_BASE + self.dma_channel * 0x40
        CH_WRITE_ADDR = CH_READ_ADDR + 0x4
        CH_TRANS_COUNT = CH_READ_ADDR + 0x8
        CH_CTRL_TRIG = CH_READ_ADDR + 0xC

        mem32[CH_READ_ADDR] = addressof(self.buffer)
        mem32[CH_WRITE_ADDR] = PIO0_TXF0
        mem32[CH_TRANS_COUNT] = BUFFER_SIZE

        ctrl = 0x3b400000 | (self.dma_channel << 11)  # Enable channel, wrap mode, incr read, size=32
        mem32[CH_CTRL_TRIG] = ctrl
        print("DMA setup completed")

    def set_frequency(self, freq):
        period = int(125_000_000 / (2 * freq))  # Half period for high and low
        print(f"Setting frequency to {freq} Hz, period: {period}")
        for i in range(0, BUFFER_SIZE, 2):
            self.buffer[i] = period
            self.buffer[i + 1] = period
        print("New buffer values calculated")

    def stop(self):
        self.sm.active(0)
        CH_CTRL_TRIG = DMA_BASE + self.dma_channel * 0x40 + 0xC
        mem32[CH_CTRL_TRIG] = 0  # Disable DMA channel
        self.pin.value(0)
        print("State Machine and DMA stopped")


# Test the simple square wave generator
try:
    print("Starting Simple Square Wave DMA test.")
    print("You should hear a 440 Hz tone, then an 880 Hz tone.")
    print("Press Ctrl+C to stop.")

    audio = SimpleSquareWaveGenerator(18)  # Use GPIO 18 for audio output

    print("Setting initial frequency")
    audio.set_frequency(440)

    print("Entering main loop")
    for i in range(10):
        print(f"Loop iteration {i + 1}")
        utime.sleep(1)
        if i == 5:
            print("Changing frequency to 880 Hz")
            audio.set_frequency(880)

except KeyboardInterrupt:
    print("Test interrupted.")

finally:
    audio.stop()
    print("Simple Square Wave DMA test stopped.")