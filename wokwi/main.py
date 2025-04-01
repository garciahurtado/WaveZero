from machine import Pin
from utime import sleep
from rp2 import PIO, asm_pio, StateMachine, DMA
from uctypes import addressof
from array import array
from sm_read_palette import read_palette
from dma import DMAChain
from sprite import generate_diagonal_stripes
from const import DEBUG_IRQ


class Screen:
    def __init__(self):
        self.start_addr = 0x20003018
        self.read_palette = None
        self.ticks_new_addr = 0
        self.sprite_bytes = generate_diagonal_stripes()
        self.setup()

    def setup(self):
        """ One time setup """
        self.led1 = Pin(6, Pin.OUT)
        self.led2 = Pin(7, Pin.OUT)
        self.led3 = Pin(8, Pin.OUT)
        self.led4 = Pin(9, Pin.OUT)

        self.leds = [self.led1, self.led2, self.led3, self.led4]
        self.dma_man = DMAChain(self.leds)

        px_count = 16  # per row
        self.out_bytes = array("L", [0] * 4 * px_count)  # 32-bit words for addresses (4bytes)

        self.read_palette = self.read_palette_init()
        self.dma_px_read = self.dma_man.init_read_dma(self.sprite_bytes)
        self.dma_px_write = self.dma_man.init_write_dma(self.out_bytes)

    def run(self):
        print("Starting Screen....")
        self.setup()

        sprite_bytes = self.sprite_bytes

        print("Diagonal Stripes Sprite (16x16, 4-bit indices, packed 2 pixels per byte):")
        for i in range(0, len(sprite_bytes), 16):
            row_bytes = sprite_bytes[i:i + 16]
            print(" ".join(f"{b:02x}" for b in row_bytes))

        print("IN 3...", end="")
        sleep(0.2)
        print(" 2...", end="")
        sleep(0.2)
        print(" 1...", end="")
        sleep(0.2)
        print("0!")
        sleep(0.2)

        self.read_palette.active(1)
        sleep(0.2)
        self.reload_addr()
        sleep(0.2)

        num = 0
        while True:
            print(f"... RUNNING FRAME [{num}]...")
            print()
            self.reset()
            self.frame()
            sleep(2)
            num += 1

    def frame(self):
        # self.read_palette.restart()
        self.reload_addr()
        self.start()
        sleep(0.5)

        print("- Debug_Bytes: ")
        for i in range(8):
            print(f"{self.out_bytes[i]:08X}-", end="")
        print()

        for i in range(8):
            print(f"{self.out_bytes[i + 8]:08X}-", end="")
        print()

    def read_palette_init(self):
        my_sm = StateMachine(0)
        my_sm.init(
            read_palette,
            sideset_base=self.led1,
        )
        my_sm.irq(handler=self.irq_sm_read_palette)
        return my_sm

    def irq_sm_read_palette(self, ch):
        if DEBUG_IRQ:
            print('<"""""""" - PIO1 SM IRQ ASSERTED - NEW ROW ADDRESS - """""""">')

        self.ticks_new_addr += 1
        if self.ticks_new_addr > 15:
            self.sm_finished = True

    def reset(self):
        # self.dma_px_read.active(0)
        # self.dma_px_write.active(0)
        self.read_palette.active(0)

    def start(self):
        self.reload_addr()
        self.read_palette.active(1)
        self.dma_px_write.active(1)
        self.dma_px_read.active(1)

    def reload_addr(self):
        # self.read_palette.active(1)
        self.read_palette.put(self.start_addr)
        # self.read_palette.active(1)

    def blink_led(self, num):
        leds = [0, self.led1, self.led2, self.led3, self.led4]
        my_led = leds[num]
        my_led.value(1)
        utime.sleep_ms(10)
        my_led.value(0)
        utime.sleep_ms(10)


print("Starting Screen....")
scr = Screen()
scr.run()
