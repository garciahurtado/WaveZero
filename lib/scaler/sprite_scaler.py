import asyncio
import time

import math

import sys

import micropython
from _rp2 import DMA, StateMachine
from uarray import array
from uctypes import addressof

from images.indexed_image import Image
from scaler.const import *
from scaler.dma_chain import DMAChain
from scaler.scaler_pio import read_palette
from scaler.scaler_debugger import ScalerDebugger
from scaler.scaler_framebuf import ScalerFramebuf
from scaler.scaling_patterns import ScalingPatterns
from profiler import Profiler as prof, timed
from sprites2.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO

prof.enabled = True

class SpriteScaler():
    def __init__(self, display):
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

        self.display:SSD1331PIO = display
        self.framebuf:ScalerFramebuf = ScalerFramebuf(display)
        self.framebuf.debug = self.debug
        self.min_write_addr = self.framebuf.min_write_addr

        self.min_read_addr = 0
        self.max_read_addr = 0
        self.max_write_addr = 0

        self.dma = DMAChain(self, display)

        self.scaled_height = 0
        self.scaled_width = 0
        self.await_addr_task = None

        self.last_sprite_class = None # for optimization
        self.base_read = 0
        self.frac_bits = 0

        self.draw_x = 0
        self.draw_y = 0
        self.alpha = None

        if self.debug_with_debug_bytes:
            print( " * DEBUG BYTES ADDR *")
            print(f" * 0x{addressof(self.debug_bytes1):08X}")
            print(f" * 0x{addressof(self.debug_bytes2):08X}")


        self.palette_addr = None

        sm_freq = 40_000_000 # must be 75% of the system freq or less, to avoid visual glitches
        # PIO1 - SM0
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=sm_freq,
        )

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

            self.dma.write_addrs[row_id] = write_addr
            self.dma.read_addrs[row_id] = read_addr
            row_id += 1

        self.dma.read_addrs[row_id] = 0x00000000 # finish it with a NULL trigger
        prof.end_profile('scaler.fill_addrs')

        if self.debug_interp_list:
            print("~~ Value Addresses ~~")
            for i in range(0, len(self.dma.write_addrs)):
                write = self.dma.write_addrs[i]
                read = self.dma.read_addrs[i]
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
        self.dma.read_finished = False

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
        prof.start_profile('scaler.interp_cfg')
        self.base_read = addressof(image.pixel_bytes)

        img_bytes = (meta.width * meta.height) // 2
        self.min_read_addr = self.base_read
        self.max_read_addr = self.min_read_addr + img_bytes
        prof.end_profile('scaler.interp_cfg')

        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(self.base_read, int(meta.width), scaled_width, scaled_height, h_scale, v_scale)
        prof.end_profile('scaler.init_interp_sprite')

        if self.debug_dma:
            print(f"Drawing a sprite of {meta.width}x{meta.height} @ base addr 0x{self.framebuf.min_write_addr:08X}")
            print(f"Hscale: x{h_scale} / Vscale: x{v_scale}")
            print(f"Sprite Stride: {meta.width}")
            print(f"Display Stride: { self.framebuf.display_stride}")

        prof.start_profile('scaler.init_pio')
        palette_addr = addressof(image.palette_bytes)
        self.init_pio(palette_addr)
        self.palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.dma.init_sprite(meta.height, meta.width, scaled_width, scaled_height, h_scale)
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


    def start(self, scaled_height):
        # This is only to avoid a mem error within the IRQ handler
        prof.start_profile('scaler.irq_color_lookup')
        prof.end_profile('scaler.irq_color_lookup')

        prof.start_profile('scaler.start_channels')

        """ Color lookup must be activated too, since it is right after a SM, so there's no direct way to trigger it"""

        self.sm_read_palette.active(1)
        self.dma.start()

        prof.end_profile('scaler.start_channels')

        while not self.dma.read_finished:
            if self.debug_with_debug_bytes:
                self.dbg.print_debug_bytes(self.debug_bytes1)

            if self.debug_dma_ch:
                print(f"\n~~ DMA CHANNELS in MAIN LOOP (Start()) (finished:{self.dma.read_finished}) ~~~~~~~~~~~\n")
                self.debug_dma_and_pio()
                print()


    def finish_sprite(self):
        prof.start_profile('scaler.finish_sprite')
        self.framebuf.blit_with_alpha(self.draw_x, self.draw_y, self.alpha)
        self.reset()

        prof.end_profile('scaler.finish_sprite')

    def init_interp(self):
        """ One time INTERPOLATOR configuration """
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

    def init_interp_sprite(self, read_base, sprite_width:int, scaled_width, scaled_height, scale_x_one = 1.0, scale_y_one = 1.0):
        frac_bits = self.frac_bits
        framebuf = self.framebuf

        if not scale_y_one:
            scale_y_one = 0.0001

        if not scale_x_one:
            scale_x_one = 0.0001

        write_base = self.min_write_addr
        frame_width = framebuf.frame_width
        frame_height = framebuf.frame_height

        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """

        """ HANDLE BOUNDS CHECK / CROPPING ------------------------  """
        """ Lane 1 config - handles integer extraction - must be reconfigured because it depends on self.frac_bits """

        self.init_interp_lane1(frac_bits, self.int_bits, framebuf.display_stride, write_base)

        if (self.draw_x >= 0) and (self.draw_y >= 0):
            """ Optimize branching for the common case """
            display_total_bytes = framebuf.frame_bytes
            self.max_write_addr = int(write_base + display_total_bytes)
        else:
            extra_bytes_x = 0
            extra_bytes_y = 0
            if self.draw_y < 0:
                if (scaled_height > frame_height):
                    """ We need to offset base_read in order to clip vertically when generating addresses """
                    extra_rows = abs(self.draw_y)
                    extra_bytes_y = (extra_rows * (sprite_width/2)) // scale_y_one
                    read_base += extra_bytes_y

                    self.draw_y = 0

            if (self.draw_x < 0): # we could probably defer this to an even lower number
                if (scaled_width > frame_width):
                    """ We need to offset base_write in order to clip horizontally when generating addresses """
                    extra_cols = abs(self.draw_x)
                    extra_px_x = int(extra_cols)
                    extra_bytes_x = (extra_px_x // scale_x_one) // 2

                    read_add = extra_bytes_x
                    # We have shorter rows now, since some of it is cropped on the left side
                    read_base += read_add

                    self.draw_x = 0

            display_total_bytes = framebuf.frame_bytes - (extra_bytes_y + extra_bytes_x)
            self.max_write_addr = int(write_base + display_total_bytes)

        # read_step_fixed = self.get_read_step_fixed(sprite_width_bytes, int(scale_x_one), frac_bits)

        # Configure remaining variables
        read_step = (sprite_width // 2) // scale_x_one
        mem32[INTERP1_BASE1] = int((1 << frac_bits) * read_step)  # Convert step to fixed point
        mem32[INTERP1_BASE2] = int(read_base) # Base sprite read address

        self.fill_addrs(scaled_height)

    @micropython.viper
    def init_interp_lane1(self, frac_bits:int, int_bits:int, display_stride:int, write_base:int):
        read_ctrl_lane1 = (
                (frac_bits << 0) |  # Shift right to get integer portion
                (frac_bits << 5) |  # Start mask at bit 0
                (int_bits << 10) |  # Full 32-bit mask to preserve address
                (0 << 15) |  # No sign extension
                (1 << 18)  # ADD_RAW - Enable raw accumulator addition
        )
        mem32[INTERP1_CTRL_LANE1] = read_ctrl_lane1

        # For write addresses we want: BASE0 + ACCUM0
        mem32[INTERP0_BASE1] = display_stride  # Row increment. Increasing beyond stride can be used to skew sprites.
        mem32[INTERP0_ACCUM0] = write_base  # Starting address

    # @micropython.viper
    # def get_read_step_fixed(self, sprite_width_bytes:int, scale_x_one:int, frac_bits:int) -> int:
    #     """ Only the devil understands this formula, but it works (not that hard, actually) """
    #
    #     read_step = sprite_width_bytes // scale_x_one
    #     """ Convert read step to fixed point """
    #     return int((1 << frac_bits) * read_step)  # Convert step to fixed point


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
        self.dma.reset()

        # Clear interpolator accumulators
        # mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0

        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0
        prof.end_profile('scaler.reset')

    def init_pio(self, palette_addr):
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)
