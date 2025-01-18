import asyncio
import time

import math

import sys

import micropython
from _rp2 import StateMachine
from uctypes import addressof

from images.indexed_image import Image
from scaler.const import *
from scaler.dma_chain import DMAChain
from scaler.scaler_pio import read_palette
from scaler.scaler_debugger import ScalerDebugger
from scaler.scaler_framebuf import ScalerFramebuf
from profiler import Profiler as prof
from sprites2.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO

prof.enabled = True

class SpriteScaler():
    def __init__(self, display):
        """ Debugging """
        self.dbg = ScalerDebugger()
        self.debug_bytes1 = self.dbg.get_debug_bytes(byte_size=2, count=32)
        self.debug_bytes2 = self.dbg.get_debug_bytes(byte_size=0, count=32)
        self.debug = True
        self.debug_dma = True
        self.debug_dma_ch = False
        self.debug_pio = False
        self.debug_irq = False
        self.debug_interp = False
        self.debug_interp_list = False
        self.debug_scale_patterns = False
        self.debug_with_debug_bytes = False

        self.write_addr2 = []

        self.display:SSD1331PIO = display
        self.framebuf:ScalerFramebuf = ScalerFramebuf(display)
        self.framebuf.debug = self.debug
        self.min_write_addr = self.framebuf.min_write_addr

        self.min_read_addr = 0
        self.row_id = 0

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

        sm_freq = 40_000_000 # must be 50% or less of the system clock, to avoid visual glitches
        # PIO1 - SM0
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=sm_freq,
        )

        self.init_interp()

    def fill_addrs(self, scaled_height):
        """ Uses INTERP to fill a sequence of Read/Write addresses indicating the start of each sprite row, and the
        start of the display row to draw it in """

        prof.start_profile("scaler.fill_addrs")

        # max_row = scaled_height
        # if max_row > self.framebuf.frame_height:
        #     max_row = self.framebuf.frame_height
        #
        # max_row = int(max_row)
        # self.dma.write_addrs[0:max_row] = self.framebuf.write_addrs_curr[0:max_row]

        """ Addr generation loop"""
        self.fill_addrs_loop(scaled_height, self.framebuf.frame_height)

        if self.debug_interp_list:
            print(f"min_write_addr: 0x{self.min_write_addr:08X} ")

            print("~~ Value Addresses ~~")
            for i in range(0, len(self.dma.write_addrs)):
                write = self.dma.write_addrs[i]
                read = self.dma.read_addrs[i]
                print(f"W [{i:02}]: 0x{write:08X}")
                print(f"R     : ....0x{read:08X}")

                if not read or not write:
                    break

        prof.end_profile("scaler.fill_addrs")

    @micropython.viper
    def fill_addrs_loop(self, scaled_height: int, frame_height: int):
        # Determine max_row with bounds checking
        max_rows = int(scaled_height)
        if max_rows > frame_height:
            max_rows = frame_height

        # Get array pointers
        write_addrs = self.dma.write_addrs  # destination
        curr_addrs = self.framebuf.write_addrs_curr  # source

        # Manual copy loop (faster than slicing in viper)
        i = 0
        while i < max_rows:
            write_addrs[i] = curr_addrs[i]
            i += 1

        row_id = 0

        """ Populate DMA with read addresses """
        while row_id < max_rows:
            read_addr = mem32[INTERP1_POP_FULL]
            self.dma.read_addrs[row_id] = read_addr
            row_id += 1

        self.dma.read_addrs[row_id] = 0x00000000 # finish it with a NULL trigger

    def draw_sprite(self, sprite:SpriteType, x, y, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """

        if self.debug:
            print(f"ABOUT TO DRAW a Sprite on x,y: {x},{y} @ H: {h_scale}x / V: {v_scale}x")

        self.draw_x = x
        self.draw_y = y
        self.alpha = sprite.alpha_color
        self.dma.read_finished = False

        if sprite.width == 16:
            self.framebuf.frac_bits = self.frac_bits = 3  # Use x.y fixed point   (16x16)
        elif sprite.width == 32:
            self.framebuf.frac_bits = self.frac_bits = 4  # Use x.y fixed point (32x32)
        else:
            print("ERROR: Max 32x32 Sprite allowed")
            sys.exit(1)
        self.int_bits = 32 - self.frac_bits

        prof.start_profile('scaler.scaled_width_height')
        scaled_height = int(sprite.height * v_scale)
        scaled_width = int(sprite.width * h_scale)
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

        self.last_sprite_class = sprite
        prof.end_profile('scaler.cache_sprite_config')

        """ Config interpolator """
        prof.start_profile('scaler.interp_cfg')
        self.base_read = addressof(image.pixel_bytes)

        self.min_read_addr = self.base_read
        prof.end_profile('scaler.interp_cfg')

        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(int(sprite.width), scaled_width, scaled_height, h_scale, v_scale)
        prof.end_profile('scaler.init_interp_sprite')

        if self.debug_dma:
            print(f"Drawing a sprite of {sprite.width}x{sprite.height} @ base addr 0x{self.framebuf.min_write_addr:08X}")
            print(f"x/y: {self.draw_x}/{self.draw_y} ")
            print(f"Hscale: x{h_scale} / Vscale: x{v_scale}")
            print(f"Sprite Stride: {sprite.width // 2}")
            print(f"Display Stride: { self.framebuf.display_stride}")

        prof.start_profile('scaler.init_pio')
        palette_addr = addressof(image.palette_bytes)
        self.init_pio(palette_addr)
        self.palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.dma.init_sprite(sprite.width, h_scale)
        prof.end_profile('scaler.init_dma_sprite')
        self.fill_addrs(scaled_height)

        if self.debug_dma:
            self.dma.debug_dma_addr()
        """ Start DMA chains and State Machines """
        self.start(scaled_height)


    def start(self, scaled_height):
        # This is only to avoid a mem error within the IRQ handler
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

    def init_interp_sprite(self, sprite_width:int, scaled_width, scaled_height, scale_x_one = 1.0, scale_y_one = 1.0):
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
        # old_draw_x = self.draw_x
        # old_base_read = self.base_read

        if self.draw_y < 0:
            if (scaled_height > frame_height):
                """ We need to offset base_read in order to clip vertically when generating addresses """
                extra_rows = abs(self.draw_y)
                extra_rows_px = math.ceil(extra_rows / scale_y_one)
                extra_bytes_y = (extra_rows_px * sprite_width) / 2
                self.base_read += int(extra_bytes_y)

                self.draw_y = 0

        if (self.draw_x < 0): # we could probably defer this to an even lower number
            if (scaled_width > frame_width):
                """ We need to offset base_read in order to clip horizontally when generating addresses """
                extra_px = abs(self.draw_x)
                extra_px_read = int(extra_px / scale_x_one)      # Extra pixels to add to the read start offset
                extra_read_bytes = int(extra_px_read / 2)   # Extra bytes to add to the base read addr (skip columns)
                extra_px_diff = extra_px - math.ceil(extra_read_bytes * scale_x_one * 2) + 3

                # We have shorter rows now, since some of it is cropped on the left side
                self.base_read += int(extra_read_bytes)

                self.draw_x = math.ceil(-extra_px_diff)
                # self.draw_x = 0

                if self.debug_dma:
                    print(f"CLIPPING: (-x)")
                    print(f"\tnew_draw_x:           {self.draw_x}")
                    print(f"\textra_px:             {extra_px}")
                    print(f"\textra_px_read:        {extra_px_read}")
                    print(f"\textra_read_bytes:     {extra_read_bytes}")
                    print(f"\textra_px_diff:        {extra_px_diff}")
                    print(f"\tbase_read after:      0x{self.base_read:08X}")

        # self.base_read += extra_bytes
        # Configure remaining variables
        read_step = (sprite_width // scale_x_one) / 2

        mem32[INTERP1_BASE1] = int((1 << frac_bits) * read_step)  # Convert step to fixed point
        mem32[INTERP1_BASE2] = int(self.base_read) # Base sprite read address

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


    def is_fifo_full(self):
        return self.sm_read_addr.tx_fifo() == 4

        fifo_status = mem32[PIO1_BASE + PIO_FSTAT]
        fifo_status = fifo_status >> 16 + 1  # Bit #1 is the flag for TX_FULL > SM 1
        fifo_full = fifo_status & 0x0000000F
        fifo_full_sm1 = fifo_full & 0b0000000000000000000000000001
        return fifo_full_sm1


    def reset(self):
        """Clean up resources before a new run"""
        self.dma.reset()

        # Clear interpolator accumulators
        mem32[INTERP0_ACCUM1] = 0

        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

        self.min_read_addr = 0
        self.row_id = 0
        self.scaled_width = 0
        self.scaled_height = 0

    def init_pio(self, palette_addr):
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)
