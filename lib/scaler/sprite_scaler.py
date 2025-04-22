import asyncio
import gc

import rp2
import time
import utime

from mpdb.mpdb import Mpdb
from scaler.scaler_framebuf import ScalerFramebuf
from scaler.status_leds import get_status_led_obj

gc.collect()

import math
import sys
import micropython
from _rp2 import StateMachine, DMA, PIO
from machine import mem32, Pin
from uctypes import addressof
from colors import color_util as colors
from scaler.const import DEBUG, DEBUG_SCALE_PATTERNS, DEBUG_DMA, DEBUG_INST, INTERP0_POP_FULL, INTERP1_POP_FULL, \
    DEBUG_DMA_ADDR, \
    INTERP0_CTRL_LANE0, INTERP0_CTRL_LANE1, INTERP0_BASE0, INTERP1_CTRL_LANE0, INTERP1_BASE0, INTERP1_ACCUM0, \
    INTERP1_ACCUM1, INTERP1_BASE1, INTERP1_BASE2, DEBUG_INTERP, INTERP1_CTRL_LANE1, INTERP0_BASE1, INTERP0_ACCUM0, \
    INTERP0_ACCUM1, DEBUG_DISPLAY, PIO0_CTRL, DEBUG_DMA_CH, DEBUG_IRQ, DEBUG_PIO, PIO1_BASE, SM0_ADDR, DEBUG_TICKS, \
    DEBUG_LED, NVIC_IPR0, NVIC_IPR1, NVIC_IPR2, NVIC_IPR3, NVIC_ISPR0, NVIC_ISER0, DEBUG_PIXELS, \
    INK_RED, INK_BLUE, INK_MAGENTA, INK_YELLOW, INK_GREEN, DMA_COLOR_ADDR_BASE, DMA_BASE, DMA_PX_READ_BASE, \
    DMA_TRANS_COUNT, PIO1_IRQ_CLEAR, IRQ0_INTS, IRQ1_INTS, IRQ0_INTE, IRQ1_INTE, IRQ0_INTF, PIO1_IRQ_FLAGS, INK_CYAN, \
    FIFO_LEVELS
from sprites2.sprite_physics import SpritePhysics

from images.indexed_image import Image
from scaler.dma_chain import DMAChain
from scaler.scaler_pio import read_palette, read_palette_init
from scaler.scaler_debugger import ScalerDebugger, printb

from sprites2.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO

from profiler import Profiler as prof
from scaler.scaler_debugger import printc

class SpriteScaler():
    def __init__(self, display):

        # NULL trigger buffer should be 2 words wide, since the px_read CH will try read 2 words for a 16px sprite
        self.null_trig_inv_buf = bytearray([255, 255, 255, 255, 255, 255, 255, 255]) # ie: 0xFFFFFFFF x2
        self.null_trig_inv_addr = addressof(self.null_trig_inv_buf)

        addr = addressof(self.null_trig_inv_buf)
        value = mem32[addr]
        unsigned_value = value & 0xFFFFFFFF

        print(f"** NULL TRIGGER BUF VALUE: 0x{unsigned_value:08X}")
        print(f"** @: 0x{self.null_trig_inv_addr:08X}")

        self.leds = get_status_led_obj()
        self.skip_rows = 0
        self.skip_cols = 0

        self.display: SSD1331PIO = display
        self.framebuf: ScalerFramebuf = ScalerFramebuf(self, display)

        jmp_pin_id = 14
        self.pin_jmp = Pin(jmp_pin_id, Pin.OUT, pull=Pin.PULL_DOWN, value=0)        # virtual GPIO

        self.dma = DMAChain(display, extra_write_addrs=self.framebuf.extra_subpx_top, jmp_pin=jmp_pin_id)

        self.dbg = ScalerDebugger()
        self.debug_bytes = self.dbg.get_debug_bytes()
        self.dma.dbg = dbg = self.dbg
        self.dma.scaler = self
        self.dma.init_channels()

        self.draw_x = 0
        self.draw_y = 0
        self.alpha = None

        self.scaled_height = 0
        self.scaled_width = 0

        self.base_read = 0
        self.read_stride_px = 0
        self.frac_bits = 0
        self.sm_ticks_new_addr = 0
        self.sm_finished = False
        self.palette_addr = None
        self.last_palette_addr = None # For caching

        self.sm_read_palette = read_palette_init(self.pin_jmp)
        self.sm_irq = self.sm_read_palette.irq(handler=self.irq_sm_read_palette, hard=True)

        self.sm_finished = False
        self.sm_read_palette.active(1)

        self.init_interp()

        if DEBUG_SCALE_PATTERNS:
            self.dma.patterns.print_patterns()

    def irq_sm_read_palette(self, sm):
        if self.sm_finished:
            raise Exception(f"This should NOT have happened - Double IRQ (ch:{sm})")

        self.sm_finished = True

        # Allow the state machine to exit the wait loop and continue back to the start
        self.pin_jmp.value(1)

        if DEBUG_IRQ:
            print('<"""""""" - PIO1 SM IRQ ASSERTED  """""""">')

    # @micropython.viper
    def fill_addrs(self, scaled_height: int, h_scale, v_scale):

        # Get array pointers
        read_addrs: [int] = self.dma.read_addrs  # destination
        write_addrs: [int] = self.dma.write_addrs  # destination

        """ Populate DMA with read addresses """
        row_id = 0
        max_read_addrs = int(self.max_read_addrs)
        while row_id < max_read_addrs:
            new_read = mem32[INTERP1_POP_FULL]
            new_write = mem32[INTERP0_POP_FULL]
            self.dma.read_addrs[row_id] = new_read
            self.dma.write_addrs[row_id] = new_write

            row_id += 1

        self.dma.read_addrs[row_id] = self.null_trig_inv_addr  # This "reverse NULL trigger" will make the SM stop. This is the address where the value lives
        self.dma.write_addrs[row_id] = new_write            # this doesnt matter, but just in case, so that px_write doesnt write to the display

        if DEBUG_DMA_ADDR:
            for row_id in range(max_read_addrs + 2):
                read_addr = self.dma.read_addrs[row_id]
                write_addr = self.dma.write_addrs[row_id]
                print(f">>> [{row_id:02.}] R: 0x{read_addr:08X}")
                print(f">>> [{row_id:02.}] W: 0x{write_addr:08X}")
                print("-------------------------")

    def draw_sprite(self, sprite:SpriteType, inst, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """
        self.reset()

        self.alpha = sprite.alpha_color
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

        prof.start_profile('scaler.draw_sprite.scaled_dims')
        scaled_height = math.ceil(sprite.height * v_scale)
        scaled_width = math.ceil(sprite.width * h_scale)
        prof.end_profile('scaler.draw_sprite.scaled_dims')

        prof.start_profile('scaler.select_buffer')
        self.scaled_height = scaled_height
        self.scaled_width = scaled_width
        self.framebuf.select_buffer(scaled_width, scaled_height)
        prof.end_profile('scaler.select_buffer')

        prof.start_profile('scaler.draw_sprite.draw_xy')
        inst.draw_x, inst.draw_y = SpritePhysics.get_draw_pos(inst, scaled_width, scaled_height)
        prof.end_profile('scaler.draw_sprite.draw_xy')

        self.draw_x = int(inst.draw_x)
        self.draw_y = int(inst.draw_y)

        if DEBUG_DISPLAY:
            print(f"ABOUT TO DRAW a Sprite on x,y: {self.draw_x},{self.draw_y} @ H: {h_scale}x / V: {v_scale}x")

        """ Config interpolator """
        self.base_read = addressof(image.pixel_bytes)
        self.init_interp_sprite(sprite.width, h_scale, v_scale)

        if DEBUG_DMA:
            print(f"PIXEL_BYTES BASE_READ: 0x{self.base_read:08X}")
            print(f"(width: {sprite.width}, hscale: {h_scale} , vscale:{v_scale})")

        prof.start_profile('scaler.fill_addrs')
        self.fill_addrs(scaled_height, h_scale, v_scale)
        prof.end_profile('scaler.fill_addrs')

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
        self.palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.dma.init_dma_counts(self.read_stride_px, scaled_height, h_scale)
        prof.end_profile('scaler.init_dma_sprite')

        if DEBUG_DMA_CH:
            print("<<< CH STATUS BEFORE START / WHILE WAIT -- draw_sprite() >>>")
            self.dma.debug_dma_channels()


        if DEBUG_TICKS:
            print(">>> TICKS BEFORE DMA/SM FINISHED:")
            self.ticks_debug()

        # ---*--- marker for bookmark - do not delete or move ---*---

        self.start()
        fifo_addr = PIO1_BASE + FIFO_LEVELS

        while not (self.sm_finished):
            utime.sleep_ms(1)

        while not (self.dma.color_lookup_finished):
            utime.sleep_ms(1)

        self.finish_sprite(image)

    def dma_pio_status(self):
        print()
        print(f"SM FINISHED:        {self.sm_finished}")
        print(f"COLOR FINISHED:     {self.dma.color_lookup_finished}")
        print(f"COLOR ACTIVE:       {self.dma.color_lookup.active()}")
        print(f"COLOR ROW COUNT:    {self.dma.color_lookup.count}")
        print()
        print(f"PX READ FINISHED:   {self.dma.px_read_finished}")
        print(f"PX READ ACTIVE:     {self.dma.px_read.active()}")
        print(f"PX_READ COUNT:      {self.dma.px_read.count}")
        print(f"PX READ READ ADDR:  0x{self.dma.px_read.read:08X}")
        print("~~~~~~~~~~~~~~~~~~~~~~~~")
        print()

        print("STATE MACHINE STATUS:")
        self.dbg.debug_pio_status(pio=1, sm=0)

    def start(self):
        """ Start DMA chains and State Machines (every frame) """
        prof.start_profile('scaler.dma_pio')
        if DEBUG_DMA:
            printc("** STARTING DMA... **", INK_GREEN)

        self.dma.start()
        prof.end_profile('scaler.dma_pio')

    def finish_sprite(self, image):
        prof.start_profile('scaler.finish_sprite')

        if DEBUG_DISPLAY:
            print(f"==> BLITTING to {self.draw_x}, {self.draw_y} / alpha: {self.alpha}")

        self.framebuf.blit_with_alpha(int(self.draw_x), int(self.draw_y), self.alpha)

        if DEBUG_PIXELS:
            print("** SPRITE SCRATCH BUFF CONTENTS RIGHT AFTER BLIT **")
            addr = self.framebuf.scratch_addr
            self.dbg.debug_sprite_rgb565(addr)

        prof.end_profile('scaler.finish_sprite')

    def ticks_debug(self):
        if DEBUG_TICKS:
            px_count = self.dma.get_sniff_data()

            print()
            printc("  ~~~   TOTAL TICKS   ~~~", INK_CYAN)
            print()
            print(f" .write_addrs:  {self.dma.ticks_write_addr}")
            print(f" .read_addrs:   {self.dma.ticks_read_addr}")
            print(f" .px_read:      {self.dma.ticks_px_read}")
            print(f" .color_row:    {self.dma.ticks_color_lookup}")
            print(f" .px_write:     {px_count}")
            print(f" .h_scale:      {self.dma.ticks_h_scale}")
            print(f" ---")
            print(f" sm_finished    {self.sm_finished}")
            print("  ~~~~~~~~~~~~~~~~~~~~~~~~")

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

    def init_interp_sprite(self, sprite_width:int, x_scale = 1.0, v_scale= 1.0):
        assert sprite_width > 0 and x_scale != 0 and v_scale != 0, "Invalid params to init_interp_sprite()!"

        prof.start_profile('scaler.init_interp_sprite.cfg')
        frac_bits = self.frac_bits
        framebuf = self.framebuf

        write_base = self.framebuf.min_write_addr

        prof.end_profile('scaler.init_interp_sprite.cfg')

        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """

        """ HANDLE BOUNDS CHECK / CROPPING ------------------------  """

        prof.start_profile('scaler.init_interp_sprite.clip')
        self.interp_clip(sprite_width, x_scale, v_scale)
        prof.end_profile('scaler.init_interp_sprite.clip')

        """ Lane 1 config - handles integer extraction - must be reconfigured because it depends on self.frac_bits """
        prof.start_profile('scaler.init_interp_sprite.lanes')
        self.init_interp_lanes(frac_bits, int(sprite_width), framebuf.display_stride, write_base)
        prof.end_profile('scaler.init_interp_sprite.lanes')

        # Configure remaining variables
        prof.start_profile('scaler.init_convert_fixed_point')

        fixed_step = self.init_convert_fixed_point(sprite_width, x_scale)
        mem32[INTERP1_BASE1] = int(fixed_step)
        mem32[INTERP1_BASE2] = self.base_read  # Base sprite read address

        if DEBUG_INTERP:
            print(f"INTERP: init_interp_sprite: INTERP1_BASE1: 0x{mem32[INTERP1_BASE1]:08X}")
            print(f"INTERP: init_interp_sprite: INTERP1_BASE2: 0x{mem32[INTERP1_BASE2]:08X}")

        if DEBUG_INTERP:
            print(f"INTERP sprite_width: {sprite_width}")
            print(f"INTERP fixed_step: {int(fixed_step)}")
            print(f"INTERP base_read: {int(self.base_read):08X}")

        prof.end_profile('scaler.init_convert_fixed_point')

    def interp_clip(self, sprite_width, x_scale, y_scale):
        """ Handles the clipping of very large sprites so that they can be rendered.
        Overflow in the Y coordinate will lead to skipping rows, and overflow in the X coordinate will lead to
        increased start addr of each row (1 byte/2px at a time) """
        framebuf = self.framebuf
        frame_width = framebuf.frame_width
        frame_height = framebuf.frame_height
        scaled_width = self.scaled_width
        scaled_height = self.scaled_height

        """ Avoid division by zero """
        if not x_scale:
            x_scale = 0.0001

        if not y_scale:
            y_scale = 0.0001

        if (self.draw_y < 0):
            self.skip_rows = skip_rows = int(abs(self.draw_y) / y_scale)
            self.draw_y += (skip_rows * y_scale)

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
            source_pixels_needed = int(skip_px_total / x_scale)
            source_pixels_skipped = min(source_pixels_needed, sprite_width)

            # 2. Align to 2px boundaries (since 2px/byte in source)
            # source_pixels_skipped = (source_pixels_skipped + 1) // 2 * 2
            skip_read_bytes = source_pixels_skipped // 2  # Bytes to skip

            # 3. Calculate actual screen position adjustment
            self.draw_x += source_pixels_skipped

            # 4. Update memory pointers (source is 2px/byte)
            # self.base_read += math.ceil(source_pixels_skipped / 2)
            # self.read_stride_px = sprite_width - source_pixels_skipped  # In pixels

            if DEBUG_INTERP:
                print(f"CLIPPING: (-X)")
                print(f"\tnew_draw_x:               {self.draw_x}")
                print(f"\tskip_px_total:            {skip_px_total}")
                print(f"\tsource_pixels_needed:     {source_pixels_needed}")
                print(f"\tsource_pixels_skipped:    {source_pixels_skipped}")
                print(f"\tskip_read_bytes:          {skip_read_bytes}")
                print(f"\tbase_read after:          0x{self.base_read:08X}")

        # Calculate visible rows after vertical clipping
        visible_rows = scaled_height - int(self.skip_rows * y_scale)
        self.max_write_addrs = min(self.framebuf.max_height, visible_rows)
        self.max_read_addrs = min(visible_rows, self.max_write_addrs)

        self.read_stride_px = sprite_width

        if DEBUG_DMA:
            print(f" + VISIBLE ROWS:    {visible_rows}")
            print(f" _  scaled_height:   {scaled_height} @{y_scale}x")
            print(f" _  max_write_addrs: {self.max_write_addrs}")
            print(f" _  max_read_addrs:  {self.max_read_addrs}")
            print(f" _  PIXEL_BYTES BASE_READ: 0x{self.base_read:08X}")

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
        assert display_stride != 0 and write_base != 0, "Invalid params to init_interp_lanes!"

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
        self.pin_jmp.value(0)

        # self.sm_read_palette.active(0)

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
        assert palette_addr != 0, "Palette address must be non-zero!"
        self.sm_read_palette.restart()

        if DEBUG_PIO:
            # Double check program counter
            addr = PIO1_BASE + SM0_ADDR
            pc = int(mem32[addr])
            print(f">--- PIO P.C.: {pc}")

        # Add a new palette address
        self.sm_finished = False
        self.sm_read_palette.put(palette_addr)

        # Raise JMP PIN to allow SM to continue
        # self.pin_jmp.value(1)


    def center_sprite(self, sprite_width, sprite_height):
        """ Helper function that returns the coordinates of the viewport that the given Sprite bounds is to be drawn at,
        in order to appear centered """
        view_width = self.display.width
        view_height = self.display.height
        x = (view_width/2) - (sprite_width/2)
        y = (view_height/2) - (sprite_height/2)
        return int(x), int(y)

    def debug_irq(self):
        print("IRQ FLAGS:")
        print("------------------------------")
        print(f"   sm_finished:     {self.sm_finished:.0}")
        print(f"   jmp_pin:         {self.pin_jmp.value()}")
        print(f"   px_read:         {self.dma.px_read_finished:.0}")
        print(f"   color_row:       {self.dma.color_lookup_finished:.0}")
        print(f"   stopper:         {self.dma.stopper_finished:.0}")
        print(f"   h_scale:         {self.dma.h_scale_finished:.0}")

        print("------------------------------")
        print()
