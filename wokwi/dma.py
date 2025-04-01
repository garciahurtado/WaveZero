from rp2 import DMA
from const import DREQ_PIO0_TX0, DREQ_PIO0_RX0, PIO0_TX0, PIO0_RX0
from uctypes import addressof
import utime


class DMAChain:
    ticks_px_read = 0
    ticks_color_row = 0
    ticks_h_scale = 0
    ticks_write_addr = 0
    ticks_read_addr = 0

    def __init__(self, leds):
        self.leds = leds
        pass

    def init_read_dma(self, sprite):
        self.sprite = sprite
        dma_px_read = DMA()

        px_read_ctrl = dma_px_read.pack_ctrl(
            size=2,
            inc_read=True,  # Through sprite data
            inc_write=True,  # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO0_TX0,
            bswap=True,
            irq_quiet=False
        )

        dma_px_read.config(
            count=4,
            read=sprite,
            write=PIO0_TX0,
            ctrl=px_read_ctrl
        )
        dma_px_read.irq(handler=self.irq_read_dma)
        return dma_px_read

    def init_write_dma(self, out_bytes):
        dma_px_write = DMA()

        px_write_ctrl = dma_px_write.pack_ctrl(
            size=2,
            inc_read=True,  # Through sprite data
            inc_write=False,  # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO0_RX0,
            bswap=True,
            irq_quiet=False
        )

        dma_px_write.config(
            count=len(out_bytes),
            read=PIO0_RX0,
            write=addressof(out_bytes),
            ctrl=px_write_ctrl
        )
        dma_px_write.irq(handler=self.irq_write_dma)
        return dma_px_write

    def irq_read_dma(self, ch):
        print("IRQ (read_dma)")

    def irq_write_dma(self, ch):
        print("IRQ (write_dma)")

    def blink_led(self, num):
        leds = [0, self.leds[0], self.leds[1], self.leds[2], self.leds[3]]
        my_led = leds[num]
        my_led.value(1)
        utime.sleep_ms(10)
        my_led.value(0)
        utime.sleep_ms(10)


