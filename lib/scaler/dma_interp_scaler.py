import asyncio
import time

import math

import sys

from _rp2 import DMA, StateMachine
from uarray import array
from uctypes import addressof

from images.indexed_image import Image
from scaler.dma_scaler_const import *
from scaler.dma_scaler_pio import read_palette
from scaler.dma_scaler_debug import ScalerDebugger
from scaler.scaler_framebuf import ScalerFramebuf
from scaler.scaling_patterns import ScalingPatterns
from profiler import Profiler as prof, timed
from sprites2.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO
from utils import aligned_buffer

ROW_ADDR_DMA_BASE = DMA_BASE_2
ROW_ADDR_TARGET_DMA_BASE = DMA_BASE_3
COLOR_LOOKUP_DMA_BASE = DMA_BASE_4
READ_DMA_BASE = DMA_BASE_5
WRITE_DMA_BASE = DMA_BASE_6
HSCALE_DMA_BASE = DMA_BASE_7

PX_READ_BYTE_SIZE = 4 # Bytes per word in the pixel reader
prof.enabled = False

class SpriteScaler():
    def __init__(self, display):
        self.addr_idx = 0
        self.display:SSD1331PIO = display
        self.framebuf = ScalerFramebuf(display)
        self.patterns = ScalingPatterns()

        """ Create array with maximum possible number of read and write addresses """
        read_buf = bytearray((display.height+2)*4)
        write_buf = aligned_buffer(display.height+2)

        self.read_addrs = array('L', read_buf)
        self.write_addrs = array('L', write_buf)

        self.min_read_addr = 0
        self.max_read_addr = 0
        self.min_write_addr = 0
        self.max_write_addr = 0

        self.rows_read_count = 0
        self.scaled_height = 0
        self.scaled_width = 0
        self.read_finished = False
        self.px_per_tx = PX_READ_BYTE_SIZE * 2
        self.await_addr_task = None

        self.last_sprite_class = None # for optimization
        self.base_read = 0
        self.frac_bits = 0

        """ Debugging """
        self.dbg = ScalerDebugger()
        self.debug_bytes1 = self.dbg.get_debug_bytes(byte_size=2, count=32)
        self.debug_bytes2 = self.dbg.get_debug_bytes(byte_size=0, count=32)
        self.debug = False
        self.debug_dma = False
        self.debug_dma_ch = False
        self.debug_pio = False
        self.debug_irq = False
        self.debug_interp = False
        self.debug_display = False
        self.debug_interp_list = False
        self.debug_scale_patterns = False
        self.debug_with_debug_bytes = False

        self.draw_x = 0
        self.draw_y = 0
        self.alpha = None

        if self.debug_with_debug_bytes:
            print( " * DEBUG BYTES ADDR *")
            print(f" * 0x{addressof(self.debug_bytes1):08X}")
            print(f" * 0x{addressof(self.debug_bytes2):08X}")

        # DMA Channels
        self.read_addr = DMA()               # 2. Vertical / row control (read and write)
        self.write_addr = DMA()        # 3. Uses ring buffer to tell read_addr where to write its address to
        self.color_lookup = DMA()           # 4. Palette color lookup / transfer
        self.px_read = DMA()            # 5. Sprite data
        self.px_write = DMA()           # 6. Display output
        self.h_scale = DMA()                # 7. Horizontal scale pattern

        self.ch_names = {
            0: None,
            1: None,
            2: "read_addr",
            3: "write_addr",
            4: "color_lookup",
            5: "px_read",
            6: "px_write",
            7: "h_scale",
        }

        self.palette_addr = None

        sm_freq = 40_000_000 # must be 75% of the system freq or less, to avoid visual glitches
        # PIO1 - SM0
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=sm_freq,
        )

        self.init_dma()
        self.init_interp()

    def fill_addrs(self, scaled_height):
        """ Uses INTERP to fill a sequence of Read/Write addresses indicating the start of each sprite row, and the
        start of the display row to draw it in """

        prof.start_profile('scaler.fill_addrs')
        max_row = int(scaled_height)
        row_id = 0

        """ Addr generation loop"""
        if self.debug_interp_list:
            print(f"max_write_addr: 0x{self.max_write_addr:08X} ")
            print(f"min_write_addr: 0x{self.min_write_addr:08X} ")

        for i in range(0, max_row):
            if self.debug_interp_list:
                print(f"idx: {i} out of {max_row} (ROW ID{row_id})")

            write_addr = mem32[INTERP0_POP_FULL]
            read_addr = mem32[INTERP1_POP_FULL]

            if write_addr > self.max_write_addr:
                """ End of address generation """
                break
            if write_addr < self.min_write_addr:
                """ by not updating the index, we are discarding "negative" write addr and its read addr """
                pass

            if write_addr >= self.min_write_addr:
                self.write_addrs[row_id] = write_addr
                self.read_addrs[row_id] = read_addr
                row_id += 1

        self.read_addrs[row_id] = 0x00000000 # finish it with a NULL trigger
        prof.end_profile('scaler.fill_addrs')

        if self.debug_interp_list:
            print("~~ Value Addresses ~~")
            for i in range(0, len(self.write_addrs)):
                write = self.write_addrs[i]
                read = self.read_addrs[i]
                print(f"W [{i:02}]: 0x{write:08X}")
                print(f"R     : ....0x{read:08X}")

    def draw_sprite(self, meta:SpriteType, x, y, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """

        if self.debug:
            print(f"ABOUT TO DRAW a Sprite on x,y: {x},{y} @ H: {h_scale}x / V: {v_scale}x")

        self.draw_x = x
        self.draw_y = y
        self.alpha = meta.alpha_color
        self.reset()
        self.read_finished = False

        prof.start_profile('scaler.scaled_width_height')
        scaled_height = meta.height * v_scale
        scaled_width = meta.width * h_scale
        prof.end_profile('scaler.scaled_width_height')

        self.framebuf.select_buffer(scaled_width, scaled_height)

        self.scaled_height = scaled_height
        self.scaled_width = scaled_width
        if self.debug:
            print("~~~ SPRITE SCALED DIMENSIONS ~~~")
            print(f" scaled_width: {scaled_width}")
            print(f" scaled_height: {scaled_height}")
        prof.end_profile('scaler.cropping')

        """ The following values can be cached from one sprite draw to the next, provided they are the same 
        Sprite type (TBD)  """
        prof.start_profile('scaler.cache_sprite_config')

        if meta.width == 32:
            self.frac_bits = 4  # Use x.y fixed point (32x32)
        elif meta.width == 16:
            self.frac_bits = 3  # Use x.y fixed point   (16x16)
        else:
            print("ERROR: only 16x16 or 32x32 sprites allowed")
            sys.exit(1)
        self.int_bits = 32 - self.frac_bits

        self.last_sprite_class = meta
        prof.end_profile('scaler.cache_sprite_config')

        """ Config interpolator """
        prof.start_profile('scaler.init_interp_sprite')
        self.base_read = addressof(image.pixel_bytes)

        img_bytes = (meta.width * meta.height) // 2
        self.min_read_addr = self.base_read
        self.max_read_addr = self.min_read_addr + img_bytes

        self.init_interp_sprite(self.base_read, meta.width, scaled_width, scaled_height, h_scale, v_scale)
        prof.end_profile('scaler.init_interp_sprite')

        if self.debug_dma:
            print(f"Drawing a sprite of {meta.width}x{meta.height} @ base addr 0x{addressof(self.framebuf.trans_framebuf):08X}")
            print(f"Hscale: x{h_scale} / Vscale: x{v_scale}")
            print(f"Sprite Stride: {meta.width}")
            print(f"Display Stride: { self.framebuf.display_stride}")

        prof.start_profile('scaler.init_pio')
        palette_addr = addressof(image.palette_bytes)
        self.init_pio(palette_addr)
        self.palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.init_dma_sprite(meta.height, meta.width, scaled_width, scaled_height, h_scale)
        prof.end_profile('scaler.init_dma_sprite')

        if self.debug_dma:
            self.dbg.debug_pio_status(sm0=True)

        if self.debug_dma:
            """ Show key addresses """

            print()
            print("~~ KEY MEMORY ADDRESSES ~~")
            print(f"    R/ ADDRS ADDR:          0x{addressof(self.read_addrs):08X}")
            print(f"    R/ ADDRS 1st:             0x{mem32[addressof(self.read_addrs)]:08X}")
            print(f"    W/ ADDRS ADDR:          0x{addressof(self.write_addrs):08X}")
            print(f"    W/ ADDRS 1st:             0x{mem32[addressof(self.write_addrs)]:08X}")

            print(f"    PALETTE ADDR:              0x{self.palette_addr:08X}")
            print(f"    SPRITE READ BASE ADDR:     0x{self.base_read:08X}")
            print()

        """ Start DMA chains and State Machines """
        self.start(scaled_height)

    def debug_dma_and_pio(self):
        self.dbg.debug_dma(self.read_addr, "read address", "read_addr", 2)
        self.dbg.debug_dma(self.write_addr, "write address", "write_addr", 3)
        self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
        self.dbg.debug_dma(self.px_read, "pixel read", "pixel_read", 5)
        self.dbg.debug_dma(self.px_write, "pixel write", "pixel_write", 6)
        self.dbg.debug_dma(self.h_scale, "horiz_scale", "horiz_scale", 7)

        if self.debug_pio:
            self.dbg.debug_pio_status(sm0=True)

    def start(self, scaled_height):
        # This is only to avoid a mem error within the IRQ handler
        prof.start_profile('scaler.irq_color_lookup')
        prof.end_profile('scaler.irq_color_lookup')

        prof.start_profile('scaler.start_channels')

        """ Color lookup must be activated too, since it is right after a SM, so there's no direct way to trigger it"""

        self.sm_read_palette.active(1)
        self.h_scale.active(1)
        self.write_addr.active(1)

        prof.end_profile('scaler.start_channels')

        while not self.read_finished:
            if self.debug_with_debug_bytes:
                self.dbg.print_debug_bytes(self.debug_bytes1)

            if self.debug_dma_ch:
                print(f"\n~~ DMA CHANNELS in MAIN LOOP (Start()) (finished:{self.read_finished}) ~~~~~~~~~~~\n")
                self.debug_dma_and_pio()
                print()


    def finish_sprite(self):
        prof.start_profile('scaler.finish_sprite')
        self.framebuf.blit_with_alpha(self.draw_x, self.draw_y, self.alpha)
        self.read_finished = True
        self.rows_read_count = 0
        self.addr_idx = 0
        self.reset()

        prof.end_profile('scaler.finish_sprite')

    def init_interp(self):
        """ One time interp configuration """
        prof.start_profile('scaler.interp_init')
        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """

        # INTERP0: Sequential Write address generation
        write_ctrl_config = (
                (0 << 0) |  # No shift needed for write addresses
                (0 << 5) |  # No mask needed
                (31 << 10) |  # Full 32-bit mask
                (0 << 15)  # No sign
        )
        mem32[INTERP0_CTRL_LANE0] = write_ctrl_config
        mem32[INTERP0_CTRL_LANE1] = write_ctrl_config
        mem32[INTERP0_BASE0] = 0  # Base address component

        # INTERP1: Read address generation with scaling
        read_ctrl_lane0 = (
                (0 << 0) |  # No shift on accumulator/raw value
                (0 << 15) |  # No sign extension
                (1 << 16) |  # CROSS_INPUT - also add ACCUM1
                (1 << 18) |  # ADD_RAW - Enable raw accumulator addition
                (1 << 20)  # CROSS_RESULT - Use other lane's result
        )
        mem32[INTERP1_CTRL_LANE0] = read_ctrl_lane0
        mem32[INTERP1_BASE0] = 0  # # Row increment in fixed point
        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

        prof.end_profile('scaler.interp_init')

    def init_interp_sprite(self, read_base, sprite_width, scaled_width, scaled_height, scale_x_one = 1.0, scale_y_one = 1.0):
        prof.start_profile('scaler.interp_sprite.start')

        frac_bits = self.frac_bits

        if not scale_y_one:
            scale_y_one = 0.0001

        if not scale_x_one:
            scale_x_one = 0.0001

        write_base = self.framebuf.trans_addr
        frame_width = self.framebuf.frame_width
        frame_height = self.framebuf.frame_height
        sprite_width_bytes = sprite_width // 2
        prof.end_profile('scaler.interp_sprite.start')

        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """

        prof.start_profile('scaler.interp_sprite.line1_cfg')

        """ Lane 1 config - handles integer extraction - must be reconfigured because it depends on self.frac_bits """
        read_ctrl_lane1 = (
                (self.frac_bits << 0) |  # Shift right to get integer portion
                (self.frac_bits << 5) |  # Start mask at bit 0
                (self.int_bits << 10) |  # Full 32-bit mask to preserve address
                (0 << 15) |  # No sign extension
                (1 << 18)  # ADD_RAW - Enable raw accumulator addition
        )
        mem32[INTERP1_CTRL_LANE1] = read_ctrl_lane1

        """ Only the devil understands this formula, but it works (not that hard, actually) """
        read_step = sprite_width_bytes / scale_y_one
        """ Convert read step to fixed point """
        read_step_fixed = int((read_step) * (1 << frac_bits))  # Convert step to fixed point

        extra_bytes_x = 0
        prof.end_profile('scaler.interp_sprite.line1_cfg')

        """ HANDLE BOUNDS CHECK / CROPPING ------------------------  """

        prof.start_profile('scaler.interp_sprite.bounds_chk')

        extra_rows = 0
        extra_bytes_x = 0
        extra_bytes_y = 0

        if self.draw_y < 0:
            if (scaled_height > self.framebuf.frame_height):
                """ We need to offset base_read in order to clip vertically when generating addresses """
                extra_rows = abs(self.draw_y)
                extra_bytes_y = (extra_rows * sprite_width) // scale_y_one
                read_base += extra_bytes_y // 2

                self.draw_y = 0

                if self.debug_interp_list:
                    print(f"NEGATIVE draw_y: extrabytes: {extra_bytes_y}")

        if (self.draw_x < 0): # we could probably defer this to an even lower number
            if (scaled_width > self.framebuf.frame_width):
                """ We need to offset base_write in order to clip horizontally when generating addresses """
                extra_cols = abs(self.draw_x)
                extra_px_x = int(extra_cols)
                extra_bytes_x = extra_px_x / scale_x_one # from scaled px to px

                # We have shorter rows now, since some of it is cropped on the left side
                read_base += (extra_bytes_x // scale_x_one)
                self.draw_x = 0

            if self.debug_interp:
                print(f"NEGATIVE draw_x: extrabytes: {extra_bytes_x} (read_step:{read_step}) / drawn at {self.draw_x}")

        display_total_bytes = int(self.framebuf.frame_height * self.framebuf.display_stride) - (extra_bytes_y + extra_bytes_x)
        self.min_write_addr = write_base
        self.max_write_addr = int(write_base + display_total_bytes)

        read_step = int(read_step)
        prof.end_profile('scaler.interp_sprite.bounds_chk')

        if self.debug_interp:
            int_bits_str = '^' * self.int_bits
            frac_bits_str = '`' * self.frac_bits
            print(f"* INTERP SPRITE INIT:")
            print(f"\t write_base:          0x{write_base:08X}")
            print(f"\t read_base:           0x{int(read_base):08X}")
            print(f"\t read step:           0x{int(read_step):08X} = {read_step}")
            print(f"\t read step (fixed):       0x{read_step_fixed:08X}")
            print(f"\t read step (fixed) b.:    {read_step_fixed:>032b}")
            print(f"\t int/frac bits:           {int_bits_str}{frac_bits_str}")
            print(f"\t scale_x:             {scale_x_one:03f}")
            print(f"\t scale_y:             {scale_y_one:03f}")
            print(f"\t sprite_row_size:     {read_step}")
            print(f"\t scaled_height:       {scaled_height}")
            print(f"\t sprite_width:        {sprite_width}")
            print(f"\t sprite_width_bytes:  {sprite_width_bytes}")
            print(f"\t display_width:       {frame_width}")
            print(f"\t extra_bytes_x:       {extra_bytes_x}")


        if self.debug_interp:
            print(f" - DISPLAY STRIDE:         { self.framebuf.display_stride} / 0x{ self.framebuf.display_stride:08X}")
            print(f" - TOTAL BYTES DISPLAY:    {display_total_bytes}")
            print(f" - MIN WRITE ADDR:         0x{self.min_write_addr:08X}")
            print(f" - MAX WRITE ADDR:         0x{self.max_write_addr:08X}")
            print(f" - MODIFIED BASE WRITE:    0x{write_base:08X}")

        prof.start_profile('scaler.interp_isprite.mem_vars')

        # For write addresses we want: BASE0 + ACCUM0
        mem32[INTERP0_BASE1] = self.framebuf.display_stride # Row increment. Increasing beyond stride can be used to skew sprites.
        mem32[INTERP0_ACCUM0] = write_base  # Starting address

        # Configure remaining variables
        mem32[INTERP1_BASE1] = read_step_fixed
        mem32[INTERP1_BASE2] = int(read_base) # Base sprite read address

        prof.end_profile('scaler.interp_isprite.mem_vars')

        self.fill_addrs(scaled_height)

        if self.debug_interp:
            print("Initial config:")
            print("INTERP0 (Write addresses):")
            print(f"  BASE0: 0x{mem32[INTERP0_BASE0]:08x}")
            print(f"  BASE1: 0x{mem32[INTERP0_BASE1]:08x}")
            print(f"  BASE2: 0x{mem32[INTERP0_BASE2]:08x}")
            print(f"  ACCU0: 0x{mem32[INTERP0_ACCUM0]:08x}")
            print(f"  ACCU1: 0x{mem32[INTERP0_ACCUM1]:08x}")

            print("INTERP1 (Read addresses):")
            print(f"  BASE0: 0x{mem32[INTERP1_BASE0]:08x}")
            print(f"  BASE1: 0x{mem32[INTERP1_BASE1]:08x}")
            print(f"  BASE2: 0x{mem32[INTERP1_BASE2]:08x}")
            print(f"  ACCU0: 0x{mem32[INTERP1_ACCUM0]:08x}")
            print(f"  ACCU1: 0x{mem32[INTERP1_ACCUM1]:08x}")

    def init_dma(self):
        """Set up the complete DMA chain for sprite scaling"""

        """ CH:2 Sprite read address DMA """
        read_addr_ctrl = self.read_addr.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=True,  # Reads from RAM
            inc_write=False,  # Fixed write target
            chain_to=self.color_lookup.channel,
        )

        self.read_addr.config(
            count=1,
            read=self.read_addrs,
            write=DMA_PX_READ_BASE + DMA_READ_ADDR_TRIG,
            ctrl=read_addr_ctrl
        )

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

        """ CH:4 Color lookup DMA """
        color_lookup_ctrl = self.color_lookup.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses
            inc_read=False,
            inc_write=False,  # always writes to DMA WRITE
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.write_addr.channel
        )

        self.color_lookup.config(
            count=1, # TBD
            read=PIO1_RX0,
            write=WRITE_DMA_BASE + DMA_READ_ADDR,
            ctrl=color_lookup_ctrl,
        )

        """ CH:5. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read.pack_ctrl(
            size=2,
            inc_read=True,      # Through sprite data
            inc_write=False,    # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO1_TX0,
            bswap=True,
            irq_quiet=True,
            chain_to=self.h_scale.channel
        )

        self.px_read.config(
            count=1,
            read=0,  # To be Set per row
            write=PIO1_TX0,
            ctrl=px_read_ctrl
        )
        self.px_read.irq(handler=self.irq_px_read_end)

        """ CH:6. Display write DMA --------------------------- """
        px_write_ctrl = self.px_write.pack_ctrl(
            size=1, # 16 bit pixels
            inc_read=False,  # from PIO
            inc_write=True,  # Through display
        )

        self.px_write.config(
            count=1,
            write=0,    # TBD - display addr
            read=0,     # TBD - palette color
            ctrl=px_write_ctrl
        )

        """ CH:7. Horiz. scale DMA --------------------------- """
        h_scale_ctrl = self.h_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            treq_sel=DREQ_PIO1_RX0,
            ring_sel=False,  # ring on read
            ring_size=4,    # n bytes = 2^n
        )

        self.h_scale.config(
            count=1,
            # read=xxx,  # Current horizontal pattern (to be set later)
            write=WRITE_DMA_BASE + DMA_TRANS_COUNT_TRIG,
            ctrl=h_scale_ctrl
        )

    def init_dma_sprite(self, height, width, scaled_width, scaled_height, h_scale=1.0):
        """ Sprite-specific DMA configuration goes here """

        prof.start_profile('scaler.dma_sprite_config')
        self.color_lookup.count = width
        self.px_read.count = width // self.px_per_tx
        prof.end_profile('scaler.dma_sprite_config')

        prof.start_profile('scaler.h_pattern')
        self.h_scale.read = self.patterns.get_pattern(h_scale)
        self.h_scale.count = width
        prof.end_profile('scaler.h_pattern')

        if self.debug_dma_ch:
            print("DMA CONFIG'D for: ")
            print(f"\t h_scale = {h_scale}")
            print(f"\t height / width = {height} / {width}")
            print(f"\t px_per_tx = {self.px_per_tx}")
            print(f"\t tx_per_row = {self.px_read.count} (px_read_dma.count)")
            print(f"\t count - color_lookup: {width}")
            print(f"\t h_scale addr:        0x{self.h_scale.read:08X}")
            print(f"\t Scaled height:        {scaled_height}")

            print()
            print("~~ DMA AFTER SPRITE CONFIG ~~~~~~~")
            self.debug_dma_and_pio()

    def irq_px_read_end(self, ch):
        if self.read_finished:
            if self.debug_irq:
                print(f"><--- PXREAD END IRQ *FALSE* ---><")
        else:
            if self.debug_irq:
                last_row_addr = self.px_read.read
                print(f"<>--- PXREAD END IRQ (Last px_read r: 0x{last_row_addr:08X})---<>")

            self.finish_sprite()

    def is_fifo_full(self):
        return self.sm_read_addr.tx_fifo() == 4

        fifo_status = mem32[PIO1_BASE + PIO_FSTAT]
        fifo_status = fifo_status >> 16 + 1  # Bit #1 is the flag for TX_FULL > SM 1
        fifo_full = fifo_status & 0x0000000F
        fifo_full_sm1 = fifo_full & 0b0000000000000000000000000001
        return fifo_full_sm1


    def reset(self):
        """Clean up resources before a new run"""
        prof.start_profile('scaler.reset')
        self.read_addr.active(0)
        self.read_addr.read = self.read_addrs

        self.write_addr.active(0)
        self.write_addr.read = self.write_addrs

        self.px_read.active(0)
        self.color_lookup.active(0)
        self.h_scale.active(0)

        self.rows_read_count = 0
        self.addr_idx = 0

        # Clear interpolator accumulators
        # mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0

        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0
        prof.end_profile('scaler.reset')

    def init_pio(self, palette_addr):
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)
