import utime

from scaler.scaler_framebuf import ScalerFramebuf
from scaler.status_leds import get_status_led_obj

import math
import sys
import micropython
from machine import mem32, Pin
from uctypes import addressof
from scaler.const import DEBUG, DEBUG_DMA, DEBUG_INST, INTERP0_POP_FULL, INTERP1_POP_FULL, \
    DEBUG_DMA_ADDR, \
    INTERP0_CTRL_LANE0, INTERP0_CTRL_LANE1, INTERP0_BASE0, INTERP1_CTRL_LANE0, INTERP1_BASE0, INTERP1_ACCUM0, \
    INTERP1_ACCUM1, INTERP1_BASE1, INTERP1_BASE2, DEBUG_INTERP, INTERP1_CTRL_LANE1, INTERP0_BASE1, INTERP0_ACCUM0, \
    INTERP0_ACCUM1, DEBUG_DISPLAY, DEBUG_TICKS, \
    DEBUG_PIXELS, \
    INK_GREEN, INK_CYAN, DEBUG_SCALES, DEBUG_INTERP_LIST, INK_BRIGHT_RED, INK_YELLOW, INK_MAGENTA, DEBUG_CLIP, DEBUG_PIO
from sprites.sprite_physics import SpritePhysics

from images.indexed_image import Image
from scaler.dma_chain import DMAChain
from scaler.scaler_pio import read_palette_init
from scaler.scaler_debugger import ScalerDebugger

from sprites.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO

from scaler.scaler_debugger import printc
from profiler import timed, prof

# GLOBAL
self_sm_finished = False

class SpriteScaler():
    def __init__(self, display):

        # NULL trigger buffer should be 2 words wide, for both 16x16 and 32x32 sprites, since it is the width of the
        # receiving DMA channel
        self.sm_read_palette_debug_msg = "(SM Read Palette IRQ handler) sm_finished = TRUE"
        self.null_trig_inv_buf = bytearray([255] * 16) # ie: 0xFFFFFFFF x2
        self.null_trig_inv_addr = addressof(self.null_trig_inv_buf)

        self.leds = get_status_led_obj()

        self.max_write_addrs = 0
        self.max_read_addrs = 0
        self.int_bits = 0

        self.display: SSD1331PIO = display
        self.framebuf: ScalerFramebuf = ScalerFramebuf(self, display)

        jmp_pin_id = 14
        self.pin_jmp = Pin(jmp_pin_id, Pin.OUT, pull=Pin.PULL_DOWN, value=0)        # virtual GPIO

        self.dma = DMAChain(display, extra_write_addrs=self.framebuf.extra_subpx_top, jmp_pin=jmp_pin_id)

        self.dbg = ScalerDebugger()
        self.debug_bytes = self.dbg.get_debug_bytes()
        self.dma.dbg = self.dbg
        self.dma.scaler = self
        self.dma.init_channels()

        self.draw_x = 0
        self.draw_y = 0
        self.alpha = None
        self.max_draw_x = 70
        self.max_draw_y = 96

        self.scaled_height = 0
        self.scaled_width = 0

        self.base_read = 0
        self.read_stride_px = 0
        self.frac_bits = 0
        self.sm_ticks_new_addr = 0
        self.palette_addr = None

        self.sm_read_palette = read_palette_init(self.pin_jmp)
        self.sm_irq = self.sm_read_palette.irq(handler=self.irq_sm_read_palette, hard=True)

        self.sm_read_palette.active(1)

        self.init_interp()

    def irq_sm_read_palette(self, sm):
        # if self_sm_finished:
        #     raise Exception(f"This SHOULD NOT have happened - Double IRQ (ch:{sm})")
        #     return False

        global self_sm_finished
        self_sm_finished = True
        if DEBUG_PIO and self_sm_finished:
            """ We have to use a class member here to avoid allocating memory in an IRQ handler"""
            print(self.sm_read_palette_debug_msg)

        # Allow the state machine to exit the wait loop and continue back to the start
        self.pin_jmp.value(1)

    @micropython.viper
    def fill_addrs(self, scaled_height: int, h_scale, v_scale):
        """ Interpolator must have already been configured for this method to work, with init_interp_sprite()
        or init_interp_lanes(), since it pulls the addresses from the interp."""

        # Get array pointers
        read_addrs = self.dma.read_addrs     # blank array we are about to fill
        write_addrs = self.dma.write_addrs   # same

        """ Populate DMA lists with read and write addresses """
        row_id: int = 0
        new_read: int = 0
        new_write: int = 0
        max_read_addrs: int = int(self.max_read_addrs)
        while row_id < max_read_addrs:
            new_read = int(mem32[INTERP1_POP_FULL])
            new_write = int(mem32[INTERP0_POP_FULL])
            read_addrs[row_id] = new_read
            write_addrs[row_id] = new_write

            row_id += 1

        read_addrs[row_id] = self.null_trig_inv_addr  # This "reverse NULL trigger" will make the SM stop. This is the address where the value lives
        write_addrs[row_id] = 0x00000000            # this doesnt matter, but just in case, so that px_write doesnt write to the display

        if DEBUG_INTERP_LIST:
            for row_id in range(max_read_addrs+1):
                read_addr = read_addrs[row_id]
                write_addr = write_addrs[row_id]
                print(f">>> [{row_id:02.}] R: 0x{read_addr:08X}")
                print(f">>> [{row_id:02.}] W: 0x{write_addr:08X}")
                print("-------------------------")

    @timed
    def draw_sprite(self, sprite: SpriteType, image: Image, x=0, y=0, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous and will not return until the whole sprite has been drawn
        Supports 16x16 and 32x32 px images only.
        """
        global self_sm_finished     # must be global because the IRQ handler loses the 'self' context

        if not h_scale or not v_scale :
            raise AttributeError("Both v_scale and h_scale must be non-zero")

        self.reset()

        """ Snap the input scale to one of the valid scale patterns """
        new_scale = self.dma.patterns.find_closest_scale(h_scale)
        h_scale = v_scale = new_scale  # we dont support independent v_scale yet because the sprite struct doesnt have the field

        self.alpha = sprite.alpha_color
        self.dma.palette_finished = False

        if DEBUG_CLIP:
            printc(f"DRAWING SPRITE @ {x},{y} (x{h_scale} scale)", INK_GREEN)

        """ Configure num of fractional bits for fixed point math as x.y (int_bits.frac_bits) """
        """ The numbers below were found by trial and error. I don't fully understand the logic behind them """
        if sprite.width == 16:
            self.frac_bits = 3      # (16x16)
            self.int_bits = 27
        elif sprite.width == 32:
            self.frac_bits = 4      # (32x32)
            self.int_bits = 28
        else:
            print(f"Only 16x16, 32x32, 16x32 or 32x16 sprites allowed, not {sprite.width}x{sprite.height}")
            sys.exit(1)

        scaled_height = math.ceil(sprite.height * v_scale)
        scaled_width = math.ceil(sprite.width * h_scale)

        if DEBUG_SCALES:
            print(f"------** SCALED DIMS FOR {type(sprite)} @ x{h_scale}**------")
            print(f"  {scaled_width}px x {scaled_height}px (w/h)")

        self.scaled_height = scaled_height
        self.scaled_width = scaled_width
        self.framebuf.select_buffer(scaled_width, scaled_height)

        self.draw_x = int(x)
        self.draw_y = int(y)

        if DEBUG_DISPLAY:
            print(f"ABOUT TO DRAW a Sprite on x,y: {self.draw_x},{self.draw_y} @ H: {h_scale}x / V: {v_scale}x")

        """ Config interpolator """
        self.base_read = addressof(image.pixel_bytes)
        ret = self.init_interp_sprite(sprite.width, h_scale, v_scale)
        if not ret: # horrible hack
            return False

        if DEBUG_DMA:
            print(f"PIXEL_BYTES BASE_READ: 0x{self.base_read:08X}")

        prof.start_profile('fill_addrs')
        try:
            self.fill_addrs(scaled_height, h_scale, v_scale)
        finally:
            prof.end_profile('fill_addrs')

        if DEBUG_DMA_ADDR:
            self.dbg.debug_dma_addrs(self.dma)

        if DEBUG_INST:
            self.dbg.debug_draw_instance(sprite, self.draw_x, self.draw_y, self.base_read, self.framebuf.min_write_addr,
                                       h_scale, v_scale, self.framebuf.display_stride)

        palette_addr = addressof(image.palette.palette)
        self.init_pio(palette_addr)
        self.palette_addr = palette_addr
        self.dma.init_dma_counts(self.read_stride_px, scaled_height, h_scale)
        self.start()

        """ We should be able to do something else while this loop runs, since the CPU is idle """
        while not (self_sm_finished and self.dma.h_scale_finished):
            utime.sleep_ms(1)

        self.finish_sprite()

    def dma_pio_status(self):
        print()
        print(f"SM FINISHED:        {self_sm_finished}")
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
        if DEBUG_DMA:
            printc("** ... STARTING DMA ... **", INK_GREEN)

        self.dma.start()

    def finish_sprite(self):
        if DEBUG_DISPLAY:
            print(f"==> BLITTING to {self.draw_x}, {self.draw_y} / alpha: {self.alpha}")

        self.framebuf.blit_with_alpha(int(self.draw_x), int(self.draw_y), self.alpha)

        if DEBUG_PIXELS:
            print("** SPRITE SCRATCH BUFF CONTENTS RIGHT AFTER BLIT **")
            addr = self.framebuf.scratch_addr
            self.dbg.debug_sprite_rgb565(addr)
        self.reset()

    def ticks_debug(self):
        if DEBUG_TICKS:
            px_count = self.dma.get_sniff_data()

            print()
            printc("  ~~~   TOTAL TICKS   ~~~", INK_CYAN)
            print()
            print(f" .write_addrs:      {self.dma.ticks_write_addr}")
            print(f" .read_addrs:       {self.dma.ticks_read_addr}")
            print(f" .px_read:          {self.dma.ticks_px_read}")
            print(f" .color_row:        {self.dma.ticks_color_lookup}")
            print(f" .px_count (sniff)  {px_count}")
            print(f" .h_scale:          {self.dma.ticks_h_scale}")
            print(f" ---")
            print(f" sm_finished        {self_sm_finished}")
            print("  ~~~~~~~~~~~~~~~~~~~~~~~~")

    def init_interp(self):
        """
        Base rp2 interpolator configuration, used for read and write address generation. Should only be needed once
        """

        # INTERP0: WRITE address generation (to framebuf)
        write_ctrl_config = (
                (0 << 0) |  # No shift needed for write addresses
                (0 << 5) |  # No mask needed
                (31 << 10) |  # Full 32-bit mask
                (0 << 15)  # No sign
        )
        mem32[INTERP0_CTRL_LANE0] = write_ctrl_config
        mem32[INTERP0_CTRL_LANE1] = write_ctrl_config
        mem32[INTERP0_BASE0] = 0  # Base address component

        # INTERP1: READ address generation (controls vertical scaling)
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

    @timed
    def init_interp_sprite(self, sprite_width:int, h_scale = 1.0, v_scale= 1.0):
        """
        Interpolator configuration that is specific to this sprite, runs every time draw_sprite is called
        """
        assert sprite_width > 0 and h_scale != 0 and v_scale != 0, "Invalid params to init_interp_sprite()!"

        frac_bits = self.frac_bits

        framebuf = self.framebuf
        write_base = self.framebuf.min_write_addr

        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """

        """ HANDLE BOUNDS CHECK / CROPPING ------------------------  """
        ret = self.clip_sprite(sprite_width, h_scale, v_scale)
        if not ret: # horrible hack
            return False

        """ LANE 1 config - handles write addresses  """
        prof.start_profile('init_interp_lanes')
        try:
            self.init_interp_lanes(frac_bits, self.int_bits, int(sprite_width), framebuf.display_stride, write_base)
        finally:
            prof.end_profile('init_interp_lanes')

        # Configure remaining variables
        fixed_step = self.init_convert_fixed_point(sprite_width, v_scale)
        fixed_step = int(fixed_step)
        mem32[INTERP1_BASE1] = fixed_step # step in fixed point notation
        mem32[INTERP1_BASE2] = self.base_read  # Base sprite read address

        if DEBUG_INTERP:
            print("- INTERPOLATOR CONFIG -")
            print(f"\tinit_interp_sprite: INTERP1_BASE2:  0x{mem32[INTERP1_BASE2]:08X} - (base read)")
            print(f"\tinit_interp_sprite: INTERP1_BASE1:  0x{mem32[INTERP1_BASE1]:08X} - (read step)")
            print(f"\tbase_read:            0x{self.base_read:08X} - INTERP1_BASE2")
            print(f"\tread_fixed_step:      0x{fixed_step:08x} - INTERP1_BASE1")
            print(f"\tread_fixed_step (b):  {fixed_step:032b}")
            print(f"\tread_fixed_step (d):  {fixed_step}")
            print(f"\tsprite_width:         {sprite_width}")
            print(f"\tv_scale:              {v_scale}")

        return True

    @micropython.viper
    def init_interp_lanes(self, frac_bits:int, int_bits:int, sprite_width:int, display_stride:int, write_base:int):
        """
        Configures interp to generate write addresses
        """
        assert display_stride != 0 and write_base != 0, "Invalid params to init_interp_lanes!"

        # Corrected MASK_LSB to 0. MASK_MSB to 31 for full range after shift.
        read_ctrl_lane1 = (
                (frac_bits << 0) |          # Shift right to get integer portion
                (frac_bits << 5) |
                (int_bits << 10) |                # 27 bit mask
                (0 << 15) |                 # No sign extension
                (1 << 18)                   # ADD_RAW - Enable raw accumulator addition
        )
        mem32[INTERP1_CTRL_LANE1] = read_ctrl_lane1

        # For write addresses we want: BASE0 + ACCUM0
        mem32[INTERP0_BASE1] = display_stride  # Per Row increment. Increasing beyond stride can be used to skew sprites.
        mem32[INTERP0_ACCUM0] = write_base  # Starting address

        if DEBUG_INTERP:
            print(f"CONFIGURED LANES WITH:")
            print(f"    WRITE BASE:     0x{write_base:08x}")
            print(f"    WRITE STRIDE:   0x{display_stride:08x}")

    @timed
    def clip_sprite(self, sprite_width, x_scale, y_scale):
        """ Handles the clipping of very large sprites so that they can be rendered.
        Overflow in the Y coordinate will lead to skipping rows, and overflow in the X coordinate will lead to
        increased start addr of each row (1 byte/2px at a time) """
        framebuf = self.framebuf
        scaled_height = self.scaled_height
        skip_rows = 0       # for Y clipping
        skip_bytes = 0      # for X clipping
        self.read_stride_px = sprite_width

        """ Avoid division by zero """
        if not x_scale:
            x_scale = 0.0001

        if not y_scale:
            y_scale = 0.0001

        """ Vertical clipping (negative Y-axis) """
        if self.draw_y < 0:
            skip_rows = int(abs(self.draw_y) / y_scale) # how many rows to skip when reading the source sprite
            self.draw_y += math.ceil(skip_rows * y_scale)

            """ We need to offset base_read in order to clip vertically when generating addresses """
            skip_bytes_y = (skip_rows * sprite_width) // 2  # Integer division

            self.base_read += skip_bytes_y

            if DEBUG_INST:
                printc(f"CLIPPING: (-Y)")
                print(f"\tnew_draw_y:           {self.draw_y}")
                print(f"\tskip_rows:            {skip_rows}")
                print(f"\tskip_bytes_y:         {skip_bytes_y}")
                print(f"\tbase_read after:      0x{self.base_read:08X}")

        """ Horizontal clipping (negative X-axis) """
        snap_px = 8  # Clip snapped to every X pixels, should also be max scale

        if self.draw_x < 0 and self.draw_x <= -snap_px:
            # Calculate needed clipping in screen pixels
            mod_x = abs(self.draw_x) % snap_px
            skip_screen_px = mod_x
            # skip_source_px = skip_screen_px // x_scale
            #
            #
            # self.draw_x += skip_source_px
            #
            # skip_bytes = (skip_source_px // 2)
            # self.read_stride_px = sprite_width - skip_source_px  # In pixels

            # self.base_read += skip_bytes
            # self.base_read = int(self.base_read)

            # 1. Convert screen skip to source pixels (original sprite resolution)
            source_pixels_needed = math.ceil(skip_screen_px / x_scale)
            source_pixels_skipped = min(source_pixels_needed, sprite_width)

            # 2. Align to 2px boundaries (since 2px/byte in source)
            source_pixels_skipped = (source_pixels_skipped + 1) // 2 * 2
            if source_pixels_skipped % 2 != 0:
                source_pixels_skipped += 1
            skip_bytes = source_pixels_skipped // 2  # Bytes to skip
            actual_screen_px_skipped = source_pixels_skipped * x_scale

            # 3. Calculate actual screen position adjustment
            self.draw_x -= actual_screen_px_skipped

            # 4. Update memory pointers (source is 2px/byte)
            self.base_read += source_pixels_skipped // 2
            self.read_stride_px = sprite_width - source_pixels_skipped  # In pixels

            if DEBUG_INST:
                printc(f"CLIPPING: (-X)")
                print(f"\tnew_draw_x:                   {self.draw_x}")
                print(f"\tskip_screen_px:               {skip_screen_px}")
                print(f"\tactual_screen_px_skipped:     {actual_screen_px_skipped}")
                print(f"\tread_stride_px:               {self.read_stride_px}")
                print(f"\tskip_read_bytes:              {skip_bytes}")
                print(f"\tbase_read after:              0x{self.base_read:08X}")

        # Calculate visible rows after vertical clipping
        visible_rows = scaled_height - int(skip_rows * y_scale)
        if visible_rows < 1:
            return False

        self.max_write_addrs = min(self.framebuf.max_height, visible_rows)
        self.max_read_addrs = min(visible_rows, self.max_write_addrs)

        self.read_stride_px = sprite_width

        if DEBUG_INST:
            print(f" + VISIBLE ROWS:    {visible_rows}")
            print(f" _  scaled_height:   {scaled_height} @{y_scale}x")
            print(f" _  max_write_addrs: {self.max_write_addrs}")
            print(f" _  max_read_addrs:  {self.max_read_addrs}")
            print(f" _  PIXEL_BYTES BASE_READ: 0x{self.base_read:08X}")

        return True

    # @micropython.viper
    @timed
    def init_convert_fixed_point(self, sprite_width, scale_y):
        """Calculate step between source rows in fixed-point."""
        fixed_step = int((sprite_width << self.frac_bits) / (scale_y * 2))
        # fixed_step = fixed_step if (fixed_step % 2 == 0) else fixed_step - 1
        return fixed_step

    @timed
    def reset(self):
        """Clean up resources before a new run"""
        self.dma.reset()
        self.pin_jmp.value(0)

        # Clear interpolator accumulators

        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0
        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

        mem32[INTERP0_BASE0] = 0
        mem32[INTERP0_BASE1] = 0
        mem32[INTERP1_BASE0] = 0
        mem32[INTERP1_BASE1] = 0

    @timed
    def init_pio(self, palette_addr):
        assert palette_addr != 0, "Palette address must be non-zero!"

        self_sm_finished = False
        self.sm_read_palette.restart()

        if self.sm_read_palette.tx_fifo() > 0:
            self.dma.debug_dma_channels()
            self.dbg.debug_all()

        # Add a new palette address
        self.sm_read_palette.put(palette_addr)

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
        print(f"   sm_finished:     {self_sm_finished:.0}")
        print(f"   jmp_pin:         {self.pin_jmp.value()}")
        print(f"   px_read:         {self.dma.px_read_finished:.0}")
        print(f"   color_row:       {self.dma.color_lookup_finished:.0}")
        print(f"   stopper:         {self.dma.stopper_finished:.0}")
        print(f"   h_scale:         {self.dma.h_scale_finished:.0}")

        print("------------------------------")
        print()
