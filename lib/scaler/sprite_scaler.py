import gc
import utime

from scaler.scaler_framebuf import ScalerFramebuf
gc.collect()

import math
import sys
import micropython
from _rp2 import StateMachine, DMA
from machine import mem32, Pin
from uctypes import addressof
from colors import color_util as colors
from scaler.const import DEBUG, DEBUG_SCALE_PATTERNS, DEBUG_DMA, DEBUG_INST, INTERP0_POP_FULL, INTERP1_POP_FULL, \
    DEBUG_DMA_ADDR, \
    INTERP0_CTRL_LANE0, INTERP0_CTRL_LANE1, INTERP0_BASE0, INTERP1_CTRL_LANE0, INTERP1_BASE0, INTERP1_ACCUM0, \
    INTERP1_ACCUM1, INTERP1_BASE1, INTERP1_BASE2, DEBUG_INTERP, INTERP1_CTRL_LANE1, INTERP0_BASE1, INTERP0_ACCUM0, \
    INTERP0_ACCUM1, DEBUG_DISPLAY, PIO0_CTRL, DEBUG_DMA_CH
from sprites2.sprite_physics import SpritePhysics

from scaler.irq_handler import IrqHandler
from images.indexed_image import Image
from scaler.dma_chain_test import DMAChain
from scaler.scaler_pio import read_palette, read_palette_init
from scaler.scaler_debugger import ScalerDebugger

from sprites2.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO

from profiler import Profiler as prof

class SpriteScaler():
    def __init__(self, display):
        self.skip_rows = 0
        self.skip_cols = 0

        if DEBUG or DEBUG_DMA:
            self.dbg = ScalerDebugger()
        else:
            self.dbg = None

        self.display:SSD1331PIO = display
        self.framebuf:ScalerFramebuf = ScalerFramebuf(display)

        self.draw_x = 0
        self.draw_y = 0
        self.alpha = None

        self.dma = DMAChain(self, display, extra_write_addrs=self.framebuf.extra_subpx_top)
        self.dma.dbg = self.dbg

        self.scaled_height = 0
        self.scaled_width = 0
        
        self.base_read = 0
        self.read_stride_px = 0
        self.frac_bits = 0

        self.palette_addr = None
        self.last_palette_addr = None # For caching
        self.sm_read_palette = read_palette_init() # Start PIO state machine

        self.init_interp()

        if DEBUG_SCALE_PATTERNS:
            self.dma.patterns.print_patterns()

        IrqHandler.dma = self.dma


    # @micropython.viper
    def fill_addrs(self, scaled_height: int, h_scale, v_scale):
        # Calculate visible rows after vertical clipping
        visible_rows = scaled_height - int(self.skip_rows * v_scale)
        max_write_addrs = min(self.framebuf.max_height, visible_rows)
        max_read_addrs = min(visible_rows, max_write_addrs)

        if DEBUG_DMA:
            print(f" + VISIBLE ROWS:    {visible_rows}")
            print(f" + scaled_height:   {scaled_height}")
            print(f" + max_write_addrs: {max_write_addrs}")
            print(f" + max_read_addrs:  {max_read_addrs}")

        # Get array pointers
        read_addrs: [int] = self.dma.read_addrs  # destination
        write_addrs: [int] = self.dma.write_addrs  # destination

        """ Populate DMA with read addresses """
        row_id = 0

        while row_id < int(max_read_addrs):
            read_addrs[row_id] = mem32[INTERP1_POP_FULL]
            write_addrs[row_id] = mem32[INTERP0_POP_FULL]

            if DEBUG_DMA_ADDR:
                print(f">>> [{row_id:02.}] R: 0x{read_addrs[row_id]:08X}")
                print(f">>> [{row_id:02.}] W: 0x{write_addrs[row_id]:08X}")
                print("-------------------------")

            row_id += 1

        read_addrs[row_id] = 0x00000000 # finish it with a NULL trigger
        write_addrs[row_id] = 0x00000000 # finish it with a NULL trigger

        if DEBUG_DMA_ADDR:
            print(f">>> [{row_id:02.}] R: 0x{read_addrs[row_id]:08X}")
            print(f">>> [{row_id:02.}] W: 0x{write_addrs[row_id]:08X}")
            print("-------------------------")
        if DEBUG_DMA:
            print(f" - TOTAL # READ ADDRS: {max_read_addrs+1}")

    def draw_sprite(self, sprite:SpriteType, inst, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """
        prof.start_profile('scaler.draw_sprite.init')

        prof.start_profile('scaler.finish_sprite.reset')
        self.reset()
        prof.end_profile('scaler.finish_sprite.reset')

        self.alpha = sprite.alpha_color
        self.dma.read_finished = False
        self.dma.palette_finished = False

        """ Configure num of fractional bits for fixed point math """
        if sprite.width == 16:
            self.frac_bits = 3 # Use x.y fixed point   (16x16)
        elif sprite.width == 32:
            self.frac_bits = 4  # Use x.y fixed point (32x32)
        else:
            print("ERROR: Max 32x32 Sprite allowed")
            sys.exit(1)
        self.int_bits = 32 - self.frac_bits
        prof.end_profile('scaler.draw_sprite.init')

        prof.start_profile('scaler.draw_sprite.scaled_dims')
        scaled_height = math.ceil(sprite.height * v_scale)
        scaled_width = math.ceil(sprite.width * h_scale)
        prof.end_profile('scaler.draw_sprite.scaled_dims')

        prof.start_profile('scaler.draw_sprite.draw_xy')
        inst.draw_x, inst.draw_y = SpritePhysics.get_draw_pos(inst, scaled_width, scaled_height)
        prof.end_profile('scaler.draw_sprite.draw_xy')

        self.draw_x = int(inst.draw_x)
        self.draw_y = int(inst.draw_y)

        if DEBUG:
            print(f"ABOUT TO DRAW a Sprite on x,y: {self.draw_x},{self.draw_y} @ H: {h_scale}x / V: {v_scale}x")

        prof.start_profile('scaler.select_buffer')
        self.framebuf.select_buffer(scaled_width, scaled_height)
        self.scaled_height = scaled_height
        self.scaled_width = scaled_width
        prof.end_profile('scaler.select_buffer')

        """ Config interpolator """
        prof.start_profile('scaler.interp_cfg')
        self.base_read = addressof(image.pixel_bytes)

        prof.end_profile('scaler.interp_cfg')

        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(int(sprite.width), h_scale, v_scale)

        if DEBUG_INST:
            coords = SpritePhysics.get_pos(inst)

            print(f"Drawing a sprite of {sprite.width}x{sprite.height} ")
            print(f"\t img_src:    0x{self.base_read:08X}")
            print(f"\t fb_target:  0x{self.framebuf.min_write_addr:08X}")
            print()
            print(f"\t x/y: {coords[0]}/{coords[1]} ")
            print(f"\t draw_x/draw_y: {self.draw_x}/{self.draw_y} ")
            print(f"\t H scale: x{h_scale} / V scale: x{v_scale}")
            print(f"\t Sprite Stride (px): {sprite.width}")
            print(f"\t Sprite Stride (bytes): {sprite.width//2}")
            print(f"\t Display Stride (fb): { self.framebuf.display_stride}")

        prof.end_profile('scaler.init_interp_sprite')
        prof.start_profile('scaler.init_pio')
        palette_addr = addressof(image.palette.palette)
        self.init_pio(palette_addr)
        self.palette_addr = self.last_palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.dma.init_sprite(self.read_stride_px, h_scale)
        prof.end_profile('scaler.init_dma_sprite')

        prof.start_profile('scaler.fill_addrs')
        visible_rows = scaled_height - math.ceil(self.skip_rows * v_scale)
        self.fill_addrs(scaled_height, visible_rows, DEBUG_DMA)

        if DEBUG_DMA:
            self.dma.debug_dma_addr()

        prof.end_profile('scaler.fill_addrs')

        self.start()

        if DEBUG_DMA_CH:
            self.dma.debug_dma_channels()

        while not (self.dma.h_scale_finished and self.dma.color_row_finished and self.dma.px_read_finished):
            if DEBUG_DMA:
                print("IRQ FLAGS:")
                print("----------------")
                print(f"   px_read:                 {self.dma.px_read_finished}")
                print(f"   color_row:               {self.dma.color_row_finished}")
                print(f"   h_scale:                 {self.dma.h_scale_finished}")
                print()
                print("--------------------------------------------------------------------")
                print()

            utime.sleep_ms(1)
            pass

        utime.sleep_ms(2)
        self.finish_sprite()

    def start(self):
        """ Start DMA chains and State Machines """
        prof.start_profile('scaler.dma_pio')
        if DEBUG:
            print("* STARTING DMA / PIO... *")

        self.dma.start()
        self.sm_read_palette.active(1)

        if DEBUG:
            print("* ...AFTER DMA / PIO START *")
        prof.end_profile('scaler.dma_pio')

    def finish_sprite(self):
        self.dma.read_finished = False
        self.dma.px_read_finished = False
        self.dma.h_scale_finished = False

        prof.start_profile('scaler.finish_sprite')
        if DEBUG_DISPLAY:
            print(f"> BLITTING to {self.draw_x}, {self.draw_y} / alpha: {self.alpha}")

        self.framebuf.blit_with_alpha(int(self.draw_x), int(self.draw_y), self.alpha)
        # self.dma.px_read.active(0)
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

    def init_interp_sprite(self, sprite_width:int, scale_x_one = 1.0, scale_y_one = 1.0):
        prof.start_profile('scaler.init_interp_sprite.cfg')
        scaled_width = self.scaled_width
        scaled_height = self.scaled_height
        frac_bits = self.frac_bits
        framebuf = self.framebuf

        write_base = self.framebuf.min_write_addr

        prof.end_profile('scaler.init_interp_sprite.cfg')

        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """

        """ HANDLE BOUNDS CHECK / CROPPING ------------------------  """

        prof.start_profile('scaler.init_interp_sprite.clip')
        self.interp_clip(sprite_width, scale_x_one, scale_y_one)
        prof.end_profile('scaler.init_interp_sprite.clip')

        """ Lane 1 config - handles integer extraction - must be reconfigured because it depends on self.frac_bits """
        prof.start_profile('scaler.init_interp_sprite.lanes')
        self.init_interp_lanes(frac_bits, int(sprite_width), framebuf.display_stride, write_base)
        prof.end_profile('scaler.init_interp_sprite.lanes')

        # Configure remaining variables
        prof.start_profile('scaler.init_convert_fixed_point')
        # frac_bits = int(self.frac_bits)
        # read_step = sprite_width / scale_x_one
        # read_step = math.ceil(read_step / 2)  # Because of 2px per byte

        fixed_step = self.init_convert_fixed_point(sprite_width, scale_x_one)
        mem32[INTERP1_BASE1] = int(fixed_step)
        mem32[INTERP1_BASE2] = self.base_read  # Base sprite read address

        # Ensure step is even
        # read_step = read_step if read_step % 2 else read_step + 1
        # fixed_step = (sprite_width << self.frac_bits) // (scale_x_one * 2)  # Convert to fixed point directly

        if DEBUG_INTERP:
            print(f"INTERP sprite_width: {sprite_width}")
            print(f"INTERP fixed_step: {int(fixed_step)}")
            print(f"INTERP base_read: {int(self.base_read):08X}")

        prof.end_profile('scaler.init_convert_fixed_point')

    def interp_clip(self, sprite_width, scale_x_one, scale_y_one):
        """ Handles the clipping of very large sprites so that they can be rendered.
        Overflow in the Y coordinate will lead to skipping rows, and overflow in the X coordinate will lead to
        increased start addr of each row (1 byte/2px at a time) """
        framebuf = self.framebuf
        frame_width = framebuf.frame_width
        frame_height = framebuf.frame_height
        scaled_width = self.scaled_width
        scaled_height = self.scaled_height
        self.read_stride_px = sprite_width

        """ Avoid division by zero """
        if not scale_x_one:
            scale_x_one = 0.0001

        if not scale_y_one:
            scale_y_one = 0.0001

        if (self.draw_y < 0):
            self.skip_rows = skip_rows = int(abs(self.draw_y) / scale_y_one)
            self.draw_y += (skip_rows * scale_y_one)

            """ We need to offset base_read in order to clip vertically when generating addresses """
            skip_bytes_y = (skip_rows * sprite_width) // 2  # Integer division

            self.base_read += math.ceil(skip_bytes_y)

            if DEBUG_INTERP:
                print(f"CLIPPING: (-Y)")
                print(f"\tnew_draw_y:           {self.draw_y}")
                print(f"\tskip_rows:            {skip_rows}")
                print(f"\tskip_bytes_y:         {skip_bytes_y}")
                print(f"\tbase_read after:      0x{self.base_read:08X}")

        """ Horizontal clipping (X-axis) """
        if self.draw_x < 0:
            # Calculate needed clipping in screen pixels
            skip_px_total = abs(self.draw_x)

            # 1. Convert screen skip to source pixels (original sprite resolution)
            source_pixels_needed = int(skip_px_total / scale_x_one)
            source_pixels_skipped = min(source_pixels_needed, sprite_width)

            # 2. Align to 2px boundaries (since 2px/byte in source)
            # source_pixels_skipped = (source_pixels_skipped + 1) // 2 * 2
            skip_read_bytes = source_pixels_skipped // 2  # Bytes to skip

            # 3. Calculate actual screen position adjustment
            self.draw_x += source_pixels_skipped

            # 4. Update memory pointers (source is 2px/byte)
            # self.base_read += math.ceil(source_pixels_skipped / 2)
            # self.read_stride_px = sprite_width - source_pixels_skipped  # In pixels
            self.read_stride_px = sprite_width

            if DEBUG_INTERP:
                print(f"CLIPPING: (-X)")
                print(f"\tnew_draw_x:               {self.draw_x}")
                print(f"\tskip_px_total:            {skip_px_total}")
                print(f"\tsource_pixels_needed:     {source_pixels_needed}")
                print(f"\tsource_pixels_skipped:    {source_pixels_skipped}")
                print(f"\tskip_read_bytes:          {skip_read_bytes}")
                print(f"\tbase_read after:          0x{self.base_read:08X}")

    # @micropython.viper
    def init_convert_fixed_point(self, sprite_width, scale_x_one):
        # Precompute constants if possible
        # Assuming sprite_width, scale_x_one, and frac_bits are constants or precomputed
        # read_step = sprite_width / scale_x_one
        # read_step = read_step / 2 # Because of 2px per byte
        # Ensure step is even
        # read_step = read_step if (read_step % 2 == 0) else read_step - 1
        fixed_step = int((sprite_width << self.frac_bits) / (scale_x_one * 2))  # Convert to fixed point directly

        # fixed_step = int((1 << frac_bits) * read_step) # Convert step to fixed point
        fixed_step = fixed_step if (fixed_step % 2 == 0) else fixed_step - 1
        return fixed_step


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
        mem32[INTERP0_BASE1] = display_stride  # Per Row increment. Increasing beyond stride can be used to skew sprites.
        mem32[INTERP0_ACCUM0] = write_base  # Starting address

    def reset(self):
        """Clean up resources before a new run"""

        self.dma.reset()

        # Clear interpolator accumulators
        prof.start_profile('scaler.finish.reset_interp')

        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0
        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

        mem32[INTERP0_BASE0] = 0
        mem32[INTERP0_BASE1] = 0
        mem32[INTERP1_BASE0] = 0
        mem32[INTERP1_BASE1] = 0

        prof.end_profile('scaler.finish.reset_interp')

        self.skip_rows = 0
        self.skip_cols = 0

    def init_pio(self, palette_addr):
        self.sm_read_palette.active(1)
        self.sm_read_palette.put(palette_addr)
        pass

    def center_sprite(self, sprite_width, sprite_height):
        """ Helper function that returns the coordinates of the viewport that the given Sprite bounds is to be drawn at,
        in order to appear centered """
        view_width = self.display.width
        view_height = self.display.height
        x = (view_width/2) - (sprite_width/2)
        y = (view_height/2) - (sprite_height/2)
        return int(x), int(y)

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
