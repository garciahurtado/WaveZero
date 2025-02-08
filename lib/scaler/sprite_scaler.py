import math
import sys
import micropython
import gc
from _rp2 import StateMachine
from time import sleep
from uctypes import addressof
from color import color_util as colors
from sprites2.sprite_physics import SpritePhysics

gc.collect()

from images.indexed_image import Image
from scaler.const import *
from scaler.dma_chain import DMAChain
from scaler.scaler_pio import read_palette
from scaler.scaler_debugger import ScalerDebugger
from scaler.scaler_framebuf import ScalerFramebuf

from sprites2.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO

from profiler import Profiler as prof

gc.collect()

class SpriteScaler():
    def __init__(self, display):
        """ Debugging """
        self.debug = False
        self.debug_dma = False
        self.debug_dma_ch = False
        self.debug_pio = False
        self.debug_irq = False
        self.debug_interp = False
        self.debug_interp_list = False
        self.debug_scale_patterns = False
        self.debug_with_debug_bytes = False

        if self.debug:
            self.dbg = ScalerDebugger()
        else:
            self.dbg = None

        self.display:SSD1331PIO = display
        self.framebuf:ScalerFramebuf = ScalerFramebuf(display)

        self.draw_x = 0
        self.draw_y = 0
        self.alpha = None

        self.dma = DMAChain(self, display)
        self.dma.dbg = self.dbg

        self.scaled_height = 0
        self.scaled_width = 0

        self.base_read = 0
        self.frac_bits = 0

        self.palette_addr = None
        self.last_palette_addr = None # For caching

        sm_freq = 40_000_000 # must be 50% or less of the system clock, to avoid visual glitches
        # PIO1 - SM0
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=sm_freq,
        )

        self.init_interp()

        if self.debug_scale_patterns:
            self.dma.patterns.print_patterns()

    @micropython.viper
    def fill_addrs(self, scaled_height: int):
        max_write_addrs = min(self.framebuf.max_height, scaled_height)
        max_read_addrs = min(scaled_height, max_write_addrs)

        # Get array pointers
        read_addrs: [int] = self.dma.read_addrs  # destination
        write_addrs: [int] = self.dma.write_addrs  # destination

        """ Populate DMA with read addresses """
        row_id = 0

        while row_id < int(max_read_addrs):
            read_addrs[row_id] = mem32[INTERP1_POP_FULL]
            write_addrs[row_id] = mem32[INTERP0_POP_FULL]
            row_id += 1

        read_addrs[row_id-1] = 0x00000000 # finish it with a NULL trigger
        write_addrs[row_id-1] = 0x00000000 # finish it with a NULL trigger
        self.dma.read_addrs = read_addrs

    def draw_sprite(self, sprite:SpriteType, inst, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """
        self.draw_x = x = inst.draw_x
        self.draw_y = y = inst.draw_y

        prof.start_profile('scaler.draw_sprite.init')
        if self.debug:
            print(f"ABOUT TO DRAW a Sprite on x,y: {x},{y} @ H: {h_scale}x / V: {v_scale}x")

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
        prof.end_profile('scaler.draw_sprite.init')

        prof.start_profile('scaler.draw_sprite.scaled_dims')
        scaled_height = int(sprite.height * v_scale)
        scaled_width = int(sprite.width * h_scale)
        prof.end_profile('scaler.draw_sprite.scaled_dims')

        prof.start_profile('scaler.select_buffer')
        self.framebuf.select_buffer(scaled_width, scaled_height)
        self.scaled_height = scaled_height
        self.scaled_width = scaled_width
        prof.end_profile('scaler.select_buffer')

        """ Config interpolator """
        prof.start_profile('scaler.interp_cfg')
        self.base_read = addressof(image.pixel_bytes)

        self.min_read_addr = self.base_read
        prof.end_profile('scaler.interp_cfg')

        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(int(sprite.width), scaled_width, scaled_height, h_scale, v_scale)

        if self.debug_dma:
            print(f"Drawing a sprite of {sprite.width}x{sprite.height} @ base addr 0x{self.framebuf.min_write_addr:08X}")
            print(f"x/y: {self.draw_x}/{self.draw_y} ")
            print(f"Hscale: x{h_scale} / Vscale: x{v_scale}")
            print(f"Sprite Stride: {sprite.width // 2}")
            print(f"Display Stride: { self.framebuf.display_stride}")

        prof.end_profile('scaler.init_interp_sprite')

        palette_addr = addressof(image.palette.palette)

        if not (palette_addr == self.last_palette_addr):
            prof.start_profile('scaler.init_pio')

            self.init_pio(palette_addr)
            self.palette_addr = self.last_palette_addr = palette_addr
            prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.dma.init_sprite(sprite.width, h_scale)
        prof.end_profile('scaler.init_dma_sprite')

        prof.start_profile('scaler.fill_addrs')
        self.fill_addrs(int(self.scaled_height))
        if self.debug_dma:
            self.dma.debug_dma_addr()

        prof.end_profile('scaler.fill_addrs')

        """ Start DMA chains and State Machines """
        prof.start_profile('scaler.dma_pio')
        self.dma.start()
        self.sm_read_palette.active(1)

        while not self.dma.read_finished:
            pass

        self.finish_sprite()

    def draw_dot(self, x, y, type):
        self.draw_x = x
        self.draw_y = y
        self.alpha = type.alpha_color

        color = type.dot_color
        color = colors.hex_to_565(color)

        self.framebuf.scratch_buffer = self.framebuf.scratch_buffer_4
        self.framebuf.frame_width = self.frame_height = 4
        display = self.framebuf.scratch_buffer

        display.pixel(0, 0, color)
        self.finish_sprite()

    def draw_fat_dot(self, x, y, type):
        """
            Draw a 2x2 pixel "dot" in lieu of the sprite image.

            Args:
                display: Display buffer object
                x (int): X coordinate for top-left of the 2x2 dot
                y (int): Y coordinate for top-left of the 2x2 dot
                color (int, optional): RGB color value. Uses sprite's dot_color if None
        """
        self.draw_x = x
        self.draw_y = y
        self.alpha = type.alpha_color

        color = type.dot_color
        color = colors.hex_to_565(color)

        self.framebuf.scratch_buffer = self.framebuf.scratch_buffer_4
        self.framebuf.frame_width = self.frame_height = 4
        display = self.framebuf.scratch_buffer

        display.pixel(0, 0, color)
        display.pixel(0 + 1, 0, color)
        display.pixel(0, 0 + 1, color)
        display.pixel(0 + 1, 0 + 1, color)
        self.finish_sprite()

    def finish_sprite(self):
        prof.end_profile('scaler.dma_pio')

        prof.start_profile('scaler.finish_sprite')
        self.framebuf.blit_with_alpha(self.draw_x, self.draw_y, self.alpha)

        prof.start_profile('scaler.finish_sprite.reset')
        self.reset()
        prof.end_profile('scaler.finish_sprite.reset')

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
        prof.start_profile('scaler.init_interp_sprite.cfg')
        frac_bits = self.frac_bits
        framebuf = self.framebuf

        """ Avoid division by zero """
        if not scale_y_one:
            scale_y_one = 0.0001

        if not scale_x_one:
            scale_x_one = 0.0001

        write_base = self.framebuf.min_write_addr
        frame_width = framebuf.frame_width
        frame_height = framebuf.frame_height
        prof.end_profile('scaler.init_interp_sprite.cfg')


        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """

        """ Lane 1 config - handles integer extraction - must be reconfigured because it depends on self.frac_bits """

        prof.start_profile('scaler.init_interp_sprite.lanes')
        self.init_interp_lanes(frac_bits, self.int_bits, framebuf.display_stride, write_base)
        prof.end_profile('scaler.init_interp_sprite.lanes')

        """ HANDLE BOUNDS CHECK / CROPPING ------------------------  """

        prof.start_profile('scaler.init_interp_sprite.clip')
        if self.draw_y < 0 and scaled_height > frame_height:
                """ We need to offset base_read in order to clip vertically when generating addresses """
                self.scaled_height += self.draw_y
                skip_rows = abs(self.draw_y)
                skip_rows = int(skip_rows / scale_y_one)
                skip_bytes_y = (skip_rows * sprite_width) // 2  # Integer division
                self.base_read += skip_bytes_y + (1 if (skip_rows * sprite_width) % 2 else 0)  # Simulate ceil

                self.draw_y = 0

        if self.draw_x < 0 and scaled_width > frame_width: # we could probably defer this to an even lower number
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

        prof.end_profile('scaler.init_interp_sprite.clip')

        # Configure remaining variables
        prof.start_profile('scaler.init_convert_fixed_point')
        self.init_convert_fixed_point(int(sprite_width), scale_x_one)
        prof.end_profile('scaler.init_convert_fixed_point')

    @micropython.viper
    def init_convert_fixed_point(self, sprite_width, scale_x_one):
        # Precompute constants if possible
        # Assuming sprite_width, scale_x_one, and frac_bits are constants or precomputed
        read_step = (int(sprite_width) << int(self.frac_bits)) // (int(scale_x_one) * 2)  # Convert to fixed point directly

        # Ensure fixed_step is even
        fixed_step = read_step if read_step % 2 == 0 else read_step - 1

        mem32[INTERP1_BASE1] = int(fixed_step)
        mem32[INTERP1_BASE2] = self.base_read  # Base sprite read address

    @micropython.viper
    def init_interp_lanes(self, frac_bits:int, int_bits:int, display_stride:int, write_base:int):
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

    def reset(self):
        """Clean up resources before a new run"""
        self.dma.reset()

        # Clear interpolator accumulators
        prof.start_profile('scaler.finish.reset_interp')

        mem32[INTERP0_ACCUM1] = 0
        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0
        prof.end_profile('scaler.finish.reset_interp')

        self.min_read_addr = 0
        self.row_id = 0
        self.scaled_width = 0
        self.scaled_height = 0

    def init_pio(self, palette_addr):
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)

    def center_sprite(self, sprite_width, sprite_height):
        """ Helper function that returns the coordinates of the viewport that the given Sprite bounds is to be drawn at,
        in order to appear centered """
        view_width = self.display.width
        view_height = self.display.height
        x = (view_width/2) - (sprite_width/2)
        y = (view_height/2) - (sprite_height/2)
        return int(x), int(y)



