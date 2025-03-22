from typing import Optional

import utime
from _rp2 import DMA
from machine import Pin
from uarray import array
from uctypes import addressof

from scaler.const import DREQ_PIO0_TX1, PIO0_TX1, DREQ_PIO0_RX1, PIO0_RX1, DREQ_PIO1_TX0, PIO1_TX0, DREQ_PIO1_RX0, \
    PIO1_RX0, DEBUG_DMA
from scaler.scaler_debugger import ScalerDebugger
from scaler.scaler_pio import read_palette_init
from ssd1331_pio import SSD1331PIO

class DMAChain:
    read_addr = None
    px_read_finished = False
    color_row_finished = False
    read_addr_finished = False
    h_scale_finished = False
    write_addr = None
    color_lookup = None
    px_read = None
    px_write = None
    h_scale = None
    dbg: Optional[ScalerDebugger] = None

    last_tick = None
    max_tick = 50 # ms
    max_read_addrs = 16
    max_write_addrs = 16
    pixel_feeder = None
    # tx_size_read = 128 # 16x16/2
    # tx_size_write = 512 # 16x16x2
    tx_size_read = 0
    tx_size_write = 0
    display_addr = 0

    def __init__(self, scaler, display:SSD1331PIO, extra_write_addrs=0):
        self.temp_2 = None
        self.temp_3 = None
        self.temp_4 = None
        self.temp_5 = None
        self.temp_6 = None
        self.temp_7 = None

        self.started = False

        """ Create array with maximum possible number of read and write addresses """
        self.read_addrs = array('L', [0] * (self.max_read_addrs + 1))
        self.write_addrs = array('L', [0] * (self.max_write_addrs + 1))
        self.dummy_px = array('B', [0])

    def init_channels(self):
        if DEBUG_DMA:
            print(" -- About to init channels ... ")

        # called only once
        self.temp_2 = DMA()  # 2. V
        self.temp_3 = DMA()  # 3. U
        self.temp_4 = DMA()  # 4. P
        self.temp_5 = DMA()  # 5. S
        self.temp_6 = DMA()  # 6. D
        self.temp_7 = DMA()  # 7. H
        self.pixel_feeder = DMA() # 8
        self.pixel_writer = DMA() # 9

        """ CH:7 pixel feeder DMA """
        pixel_feeder_ctrl = self.pixel_feeder.pack_ctrl(
            size=0,# 1byte at a time
            inc_read=False,  # No actual sprite data
            inc_write=False,  # goes to SM FIFO
            treq_sel=DREQ_PIO1_TX0,
            bswap=True,
        )

        self.pixel_feeder.config(
            count=self.tx_size_read,
            read=addressof(self.dummy_px),
            write=PIO1_TX0,
            ctrl=pixel_feeder_ctrl,
        )

        """ CH:8 pixel writer DMA """
        pixel_writer_ctrl = self.pixel_writer.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses
            inc_read=True,
            inc_write=True,
            treq_sel=DREQ_PIO1_RX0,
        )

        self.pixel_writer.config(
            count=self.tx_size_write,
            read=addressof(self.dummy_px),
            write=0, # TBD
            ctrl=pixel_writer_ctrl,
        )

        if DEBUG_DMA:
            print(" ... DMA channels initialized / ")

        pass

    def start(self):
        if DEBUG_DMA:
            print(" . Starting SM and DMA ... ")

        self.last_tick = utime.ticks_ms()
        self.started = True

        self.pixel_feeder.read = addressof(self.read_addrs)

        self.pixel_feeder.active(1)
        self.pixel_writer.active(1)

        self.px_read_finished = False
        self.color_row_finished = False
        self.h_scale_finished = False

        self.pixel_feeder.active(0)
        self.pixel_feeder.count = self.tx_size_read

        self.pixel_writer.active(0)
        self.pixel_writer.count = self.tx_size_write
        self.pixel_writer.write = self.display_addr

        if DEBUG_DMA:
            print(" ... SM and DMA Started. / ")

        utime.sleep_ms(3)

    def is_finished(self):
        utime.sleep_ms(5)
        return True

        if utime.ticks_diff(utime.ticks_ms(), self.last_tick) > self.max_tick:
            utime.sleep_ms(1)
            return True
        else:
            utime.sleep_ms(1)
            return False

    def reset(self):
        utime.sleep_ms(2)
        self.px_read_finished = False
        self.color_row_finished = False
        self.h_scale_finished = False
        self.started = False

        self.pixel_feeder.active(0)
        self.pixel_writer.active(0)

    def init_sprite(self, read_stride_px, h_scale):
        utime.sleep_ms(2)
        pass

    def init_display_addr(self, disp_addr):
        self.display_addr = disp_addr
        self.pixel_writer.write = self.display_addr


    def debug_dma_addr(self):
        pass

    def debug_dma_channels(self):
        return False
