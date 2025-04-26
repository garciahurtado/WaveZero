import math
import micropython
import sys
from machine import mem32, Pin

micropython.alloc_emergency_exception_buf(100)
from _rp2 import DMA
from uarray import array
from uctypes import addressof

from scaler.const import *
from scaler.scale_patterns import ScalePatterns
from scaler.status_leds import get_status_led_obj
from ssd1331_pio import SSD1331PIO
from scaler.scaler_debugger import ScalerDebugger
from typing import Optional

COLOR_LOOKUP_DMA_BASE = DMA_BASE_4
READ_DMA_BASE = DMA_BASE_5
WRITE_DMA_BASE = DMA_BASE_6
HSCALE_DMA_BASE = DMA_BASE_7
PX_READ_BYTE_SIZE = 4 # Bytes per word in the pixel reader
class DMAChain:
    px_read_finished = False
    color_lookup_finished = False
    h_scale_finished = False
    read_addr_finished = False
    write_addr_finished = False
    addr_list_finished = False
    stopper_finished = False

    ticks_px_read = 0
    ticks_color_lookup = 0
    ticks_h_scale = 0
    ticks_write_addr = 0
    ticks_read_addr = 0

    read_addr = None
    write_addr = None
    color_lookup = None
    px_read = None
    px_write = None
    h_scale = None
    addr_loader = None
    leds = None
    scaler = None

    dbg: Optional[ScalerDebugger] = None
    debug_bytes = None

    def __init__(self, display:SSD1331PIO, extra_write_addrs=0, jmp_pin:int=0):
        """ extra_read_addrs: additional rows in the margin of the full screen buffer"""

        self.max_sprite_height = 72
        self.max_write_addrs = self.max_read_addrs = display.HEIGHT + extra_write_addrs

        self.patterns = ScalePatterns()

        """ Create array with maximum possible number of read and write addresses """
        self.read_addrs = array('L', [0] * (self.max_read_addrs+1))
        self.write_addrs = array('L', [0] * (self.max_write_addrs+1))

        """ Status GPIO register value to enable """
        # gpio_set_bits = 0x00000000 | (1 << (jmp_pin-1))
        # gpio_clear_bits = 0x00000000 | (1 << (jmp_pin-1))
        # self.jmp_clear_value = array('L', gpio_clear_bits.to_bytes(4, "little"))
        #
        # self.leds = get_status_led_obj()

        self.init_sniffer()


    def init_channels(self):
        """Initialize the complete DMA chain for sprite scaling."""
        """ Acquire hardware DMA channels """
        self.read_addr = DMA()      #2. Vertical / row control (read and write)
        self.write_addr = DMA()     #3. Uses ring buffer to tell read_addr where to write its address to
        self.px_read = DMA()        #4. Sprite data
        self.color_lookup = DMA()   #5. Palette color lookup / transfer
        self.px_write = DMA()       #6. Display output
        self.h_scale = DMA()        #7. Horizontal scale pattern

        self.init_read_addr()
        self.init_write_addr()
        self.init_color_lookup()
        self.init_px_read()
        self.init_px_write()
        self.init_h_scale()

    def init_write_addr(self):
        """ CH:3 Display write address DMA """
        write_addr_ctrl = self.write_addr.pack_ctrl(
            size=2,             # 32-bit control blocks
            inc_read=True,      # Step through write addrs
            inc_write=False,    # always write to PX WRITE DMA
            irq_quiet=False,
            chain_to=self.read_addr.channel,
        )

        self.write_addr.config(
            count=1,
            read=addressof(self.write_addrs),          # read/write TARGET address block array
            write=DMA_PX_WRITE_BASE + DMA_WRITE_ADDR,
            ctrl=write_addr_ctrl,
        )
        self.write_addr.irq(handler=self.irq_write_addr, hard=True)
    #

    def init_read_addr(self):
        """ CH:2 Sprite read address DMA """
        read_addr_ctrl = self.read_addr.pack_ctrl(
            size=2,             # 32-bit control blocks
            inc_read=True,      # Reads from RAM
            inc_write=False,    # Fixed write target
            irq_quiet=False,
            chain_to = self.h_scale.channel, # No chain
        )

        self.read_addr.config(
            count=1,
            read=self.read_addrs,
            write=DMA_PX_READ_BASE + DMA_READ_ADDR_TRIG,
            ctrl=read_addr_ctrl
        )
        self.read_addr.irq(handler=self.irq_read_addr, hard=True)

    def init_px_read(self):
        """ CH:4. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read.pack_ctrl(
            size=2,
            inc_read=True,      # Through sprite data
            inc_write=False,    # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO1_TX0,
            bswap=True,
            irq_quiet=False,
            chain_to=self.px_read.channel,
        )

        self.px_read.config(
            count=1,
            read=0,  # To be Set per row
            write=PIO1_TX0,
            ctrl=px_read_ctrl
        )
        self.px_read.irq(handler=self.irq_px_read_end, hard=True)

    def init_color_lookup(self):
        """ CH:5 Color lookup DMA """
        color_lookup_ctrl = self.color_lookup.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses point to them
            inc_read=False,
            inc_write=False,  # always writes to DMA6 READ
            treq_sel=DREQ_PIO1_RX0,
            irq_quiet=False,
            chain_to=self.write_addr.channel,
        )

        self.color_lookup.config(
            count=1,  # TBD
            read=PIO1_RX0,
            write=DMA_PX_WRITE_BASE + DMA_READ_ADDR,
            ctrl=color_lookup_ctrl,
        )
        self.color_lookup.irq(handler=self.irq_color_lookup, hard=True)

    def init_px_write(self):
        """ CH:6. Display write DMA --------------------------- """
        px_write_ctrl = self.px_write.pack_ctrl(
            size=1,  # 16 bit pixels
            inc_read=False,  # from PIO
            inc_write=True,  # Through display
            irq_quiet=True,
            chain_to=self.px_write.channel,
        )

        self.px_write.config(
            count=1,
            write=0,  # TBD - display addr
            read=0,  # TBD - palette color
            ctrl=px_write_ctrl
        )

    def init_h_scale(self):
        """ CH:7. Horiz. scale DMA --------------------------- """
        h_scale_ctrl = self.h_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            ring_sel=False,  # ring on read
            ring_size=4,  # n bytes = 2^n
            irq_quiet=False,
            sniff_en=True,
            chain_to=self.write_addr.channel,
            treq_sel=DREQ_PIO1_RX0,
        )

        self.h_scale.config(
            count=0,
            # read=xxx,  # Current horizontal pattern (to be set later)
            write=DMA_PX_WRITE_BASE + DMA_TRANS_COUNT_TRIG,
            ctrl=h_scale_ctrl
        )
        self.h_scale.irq(handler=self.irq_h_scale, hard=True)

    def init_dma_counts(self, read_stride_px, num_rows, h_scale):
        """Configure Sprite specific DMA parameters."""
        total_px = read_stride_px * num_rows

        self.color_lookup.count = total_px
        px_read_tx_count = int(read_stride_px / 8) # 2px per byte * 4 bytes per word = 8px per word
        self.px_read.count = px_read_tx_count
        # self.h_scale.count = 1
        self.h_scale.count = read_stride_px
        self.h_scale.read = self.patterns.get_pattern(h_scale)

        if DEBUG_DMA:
            print(">> -- COUNTS --")
            print(f">> Num rows:               {num_rows}")
            print(f">> readstride in PX:       {read_stride_px}")
            print(f">> Total PX:               {read_stride_px * num_rows}")
            print(f">> px_read.DMA.count (tx): {px_read_tx_count}")

    def start(self):
        self.px_read_finished = False
        self.color_lookup_finished = False
        self.read_addr_finished = False
        self.write_addr_finished = False
        self.h_scale_finished = False
        self.addr_list_finished = False
        self.stopper_finished = False

        self.color_lookup.active(1)
        self.write_addr.active(1) # write_addr kicks off the whole sequence
        pass

    def reset(self):
        self.px_read.active(0)
        self.color_lookup.active(0)
        self.h_scale.active(0)

        self.ticks_px_read = 0
        self.ticks_color_lookup = 0
        self.ticks_h_scale = 0
        self.ticks_read_addr = 0
        self.ticks_write_addr = 0

        self.write_addr.read = addressof(self.write_addrs)
        self.read_addr.read = addressof(self.read_addrs)
        self.reset_sniffer()

    def irq_px_read_end(self, ch):
        """IRQ Handler for pixels read per row"""
        self.ticks_px_read += 1
        self.px_read_finished = True

    def irq_color_lookup(self, ch):
        self.color_lookup_finished = True
        self.ticks_color_lookup += 1

    def irq_h_scale(self, ch):
        self.h_scale_finished = True
        self.ticks_h_scale += 1

    def irq_write_addr(self, ch):
        self.ticks_write_addr += 1
        self.write_addr_finished = True

    def irq_read_addr(self, ch):
        self.ticks_read_addr += 1
        self.read_addr_finished = True

    def debug_dma_channels(self, full=False):
        # self.dbg.debug_dma(self.scaler.display.dma0, "display render", "disp_addr", 0)
        # self.dbg.debug_dma(self.scaler.display.dma1, "display ctrl", "disp_ctrl", 1)
        self.dbg.debug_dma(self.read_addr, "read_addr", full=full)
        self.dbg.debug_dma(self.write_addr, "write_addr", full=full)
        self.dbg.debug_dma(self.px_read, "pixel_read", full=full)
        self.dbg.debug_dma(self.color_lookup, "color_lookup", full=full)
        self.dbg.debug_dma(self.px_write, "pixel_write", full=full)
        self.dbg.debug_dma(self.h_scale, "horiz_scale", full=full)
    def get_sniff_data(self):
        addr = DMA_BASE + DMA_SNIFF_DATA
        value = mem32[addr] & 0xffffffff

        return value

    def init_sniffer(self):
        """
        Configure sniffer for simple sum on a specific DMA Channel. That channels configuration needs to contain
        sniff_en=True
        """

        addr1 = DMA_BASE + DMA_SNIFF_CTRL
        value = mem32[addr1]
        value = 0b111101111     # ..01101: CH.6 / ..01111: CH.7
        mem32[addr1] = value

        self.reset_sniffer()

        if DEBUG:
            value1 = mem32[addr1]
            print(f" > SNIFF CTRL: 0b{value1:032b} @ 0x{addr1:08X}")

    def reset_sniffer(self):
        addr = DMA_BASE + DMA_SNIFF_DATA
        mem32[addr] = 0x00000000

    def print_debug_bytes(self):
        self.dbg.print_debug_bytes(self.debug_bytes)
