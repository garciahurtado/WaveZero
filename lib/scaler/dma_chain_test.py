import math

import utime
from _rp2 import DMA
from uarray import array
from uctypes import addressof

from scaler.const import *
from scaler.scale_patterns import ScalePatterns
from ssd1331_pio import SSD1331PIO

COLOR_LOOKUP_DMA_BASE = DMA_BASE_4
READ_DMA_BASE = DMA_BASE_5
WRITE_DMA_BASE = DMA_BASE_6
HSCALE_DMA_BASE = DMA_BASE_7
PX_READ_BYTE_SIZE = 4 # Bytes per word in the pixel reader

test_dma = None

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

    def __init__(self, scaler, display:SSD1331PIO, extra_write_addrs=0):
        """ extra_read_addrs: additional rows in the margin of the full screen buffer"""
        self.dbg = None
        self.scaler = scaler
        self.px_per_tx = PX_READ_BYTE_SIZE * 2
        self.read_count = 0
        self.addr_idx = 0
        self.max_sprite_height = 32
        self.max_write_addrs = self.max_read_addrs = display.HEIGHT + extra_write_addrs

        self.patterns = ScalePatterns()

        """ Create array with maximum possible number of read and write addresses """
        self.read_addrs = array('L', [0] * (self.max_read_addrs+1))
        self.write_addrs = array('L', [0] * (self.max_write_addrs+1))

    def init_channels(self):
        """Initialize the complete DMA chain for sprite scaling."""
        """ Acquire hardware DMA channels """
        self.read_addr = DMA()      #2. Vertical / row control (read and write)
        self.write_addr = DMA()     #3. Uses ring buffer to tell read_addr where to write its address to
        self.color_lookup = DMA()   #4. Palette color lookup / transfer
        self.px_read = DMA()        #5. Sprite data
        self.px_write = DMA()       #6. Display output
        self.h_scale = DMA()        #7. Horizontal scale pattern

        self.init_read_addr()
        self.init_write_addr()
        self.init_color_lookup()
        self.init_px_read()
        self.init_px_write()
        self.init_h_scale()


    def init_read_addr(self):
        """ CH:2 Sprite read address DMA """
        read_addr_ctrl = self.read_addr.pack_ctrl(
            size=2,             # 32-bit control blocks
            inc_read=True,      # Reads from RAM
            inc_write=False,    # Fixed write target
            chain_to=self.color_lookup.channel,
        )

        self.read_addr.config(
            count=1,
            read=self.read_addrs,
            write=DMA_PX_READ_BASE + DMA_READ_ADDR_TRIG,
            ctrl=read_addr_ctrl
        )
        # self.read_addr.irq(handler=self.irq_end_read_addr)

    def init_write_addr(self):
        """ CH:3 Display write address DMA """
        write_addr_ctrl = self.write_addr.pack_ctrl(
            size=2,             # 32-bit control blocks
            inc_read=True,      # Step through write addrs
            inc_write=False,    # always write to DMA2 WRITE
            chain_to=self.read_addr.channel,
        )

        self.write_addr.config(
            count=1,
            read=addressof(self.write_addrs),          # read/write TARGET address block array
            write=DMA_PX_WRITE_BASE + DMA_WRITE_ADDR,
            ctrl=write_addr_ctrl,
        )

    def init_color_lookup(self):
        """ CH:4 Color lookup DMA """
        color_lookup_ctrl = self.color_lookup.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses
            inc_read=False,
            inc_write=False,  # always writes to DMA WRITE
            treq_sel=DREQ_PIO0_RX1,
            chain_to=self.write_addr.channel,
            irq_quiet=False
        )

        self.color_lookup.config(
            count=1,  # TBD
            read=PIO0_RX1,
            write=DMA_PX_WRITE_BASE + DMA_READ_ADDR,
            ctrl=color_lookup_ctrl,
        )
        self.color_lookup.irq(handler=self.irq_end_row)


    def init_px_read(self):
        """ CH:5. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read.pack_ctrl(
            size=0,
            inc_read=True,      # Through sprite data
            inc_write=False,    # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO0_TX1,
            bswap=True,
            irq_quiet=False,
            chain_to=self.h_scale.channel
        )

        self.px_read.config(
            count=1,
            read=0,  # To be Set per row
            write=PIO0_TX1,
            ctrl=px_read_ctrl
        )
        self.px_read.irq(handler=self.irq_px_read)

    def init_px_write(self):
        """ CH:6. Display write DMA --------------------------- """
        px_write_ctrl = self.px_write.pack_ctrl(
            size=1,  # 16 bit pixels
            inc_read=False,  # from PIO
            inc_write=True,  # Through display
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
            treq_sel=DREQ_PIO0_RX1,
            ring_sel=False,  # ring on read
            ring_size=4,  # n bytes = 2^n
            irq_quiet=False
        )

        self.h_scale.config(
            count=1,
            # read=xxx,  # Current horizontal pattern (to be set later)
            write=DMA_PX_WRITE_BASE + DMA_TRANS_COUNT_TRIG,
            ctrl=h_scale_ctrl
        )
        self.h_scale.irq(handler=self.irq_h_scale)

    def init_sprite(self, read_stride_px, h_scale):
        """Configure Sprite specific DMA parameters."""
        self.color_lookup.count = read_stride_px
        self.px_read.count = int(read_stride_px / 2)
        self.h_scale.count = read_stride_px
        self.h_scale.read = self.patterns.get_pattern(h_scale)

    def start(self):
        """Activate DMA channels in correct sequence."""

        self.px_read_finished = False
        self.color_row_finished = False
        self.read_addr_finished = False
        self.h_scale_finished = False

        self.write_addr.active(1)

    def reset(self):
        """Reset all DMA channels."""
        self.read_addr.active(0)
        self.write_addr.active(0)
        self.px_read.active(0)
        self.color_lookup.active(0)
        self.h_scale.active(0)

        # Reset counts
        self.read_count = 0
        self.addr_idx = 0
        #

        while (self.write_addr.active() or self.read_addr.active()):
            pass

        # Reset address list pointers
        self.write_addr.read = addressof(self.write_addrs)
        self.read_addr.read = addressof(self.read_addrs)


    def irq_px_read(self, ch):
        """IRQ Handler for end of ALL pixels read"""
        if DEBUG_IRQ:
            print("* IRQ PX ROW READ END *")
        self.px_read_finished = True

    def irq_end_row(self, ch):
        if DEBUG_IRQ:
            print("-x- IRQ COLOR ROW END  -x-")
        self.color_row_finished = True

    def irq_end_read_addr(self, ch):
        if DEBUG_IRQ:
            print("_-_ IRQ END READ ADDRs _-_")
        self.read_addr_finished = True

    def irq_h_scale(self, ch):
        if DEBUG_IRQ:
            print("=== IRQ END HORIZ SCALE ===")
        self.h_scale_finished = True

    def is_finished(self):
        # if (self.read_addr_finished and
        if (self.px_read_finished and
            self.color_row_finished and
            self.h_scale_finished
        ):
            return True
        else:
            return False

    def debug_dma_channels(self):
        # self.dbg.debug_dma(self.disp_addr, "display driver address", "disp_addr", 0)
        # self.dbg.debug_dma(self.dist_ctrl, "display driver ctrl", "disp_ctrl", 1)
        self.dbg.debug_dma(self.read_addr, "read address", "read_addr", 2)
        self.dbg.debug_dma(self.write_addr, "write address", "write_addr", 3)
        self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
        self.dbg.debug_dma(self.px_read, "pixel read", "pixel_read", 5)
        self.dbg.debug_dma(self.px_write, "pixel write", "pixel_write", 6)
        self.dbg.debug_dma(self.h_scale, "horiz_scale", "horiz_scale", 7)

    def debug_dma_addr(self):

        """ Show key addresses """
        print()
        print("~~ KEY MEMORY ADDRESSES ~~")
        print(f"    R/ ADDRS ADDR:          0x{addressof(self.read_addrs):08X}")
        print(f"    R/ ADDRS 1st:             0x{mem32[addressof(self.read_addrs)]:08X}")
        print(f"    W/ ADDRS ADDR:          0x{addressof(self.write_addrs):08X}")
        print(f"    W/ ADDRS 1st:             0x{mem32[addressof(self.write_addrs)]:08X}")
        print()


