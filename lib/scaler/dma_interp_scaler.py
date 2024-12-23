import time

import math

from _rp2 import DMA, StateMachine
from uarray import array
from uctypes import addressof

from images.indexed_image import Image
from scaler.dma_scaler_const import *
from scaler.dma_scaler_pio import read_palette, read_addr
from scaler.dma_scaler_debug import ScalerDebugger
from profiler import Profiler as prof, timed
from sprites2.sprite_types import SpriteType
from utils import aligned_buffer

ROW_ADDR_DMA_BASE = DMA_BASE_2
ROW_ADDR_TARGET_DMA_BASE = DMA_BASE_3
COLOR_LOOKUP_DMA_BASE = DMA_BASE_4
READ_DMA_BASE = DMA_BASE_5
WRITE_DMA_BASE = DMA_BASE_6
HSCALE_DMA_BASE = DMA_BASE_7

PX_READ_BYTE_SIZE = 4 # Bytes per word in the pixel reader

class SpriteScaler():
    def __init__(self, display):
        self.display = display
        self.read_blocks = []
        self.write_blocks = None
        self.h_patterns = {}

        """ Create array with maximum possible number of addresses """
        self.value_addrs = array('L', [0] * (display.height * 2))
        self.value_addr_ptr = None
        self.rows_read_count = 0
        self.scaled_height = 0
        self.read_finished = False

        self.dbg = ScalerDebugger()
        self.debug_bytes1 = self.dbg.get_debug_bytes(byte_size=2, count=32)
        self.debug_bytes2 = self.dbg.get_debug_bytes(byte_size=0, count=32)
        self.debug = False
        self.debug_dma = False
        self.debug_interp = False
        self.debug_interp_list = False
        self.debug_with_debug_bytes = False

        self.display_stride = self.display.width * 2
        display_pixels = (self.display.height) * self.display_stride
        self.max_write_addr = self.display.write_addr + display_pixels

        """" Add two blocks, one for the pixel reader READ addr, and one for the pixel writer WRITE addr """
        self.target_addrs = array('L', [0]*2)

        # Write addr, then read addr + trigger
        self.target_addrs[0] = int(DMA_BASE_6 + DMA_WRITE_ADDR)
        self.target_addrs[1] = int(DMA_BASE_5 + DMA_READ_ADDR_TRIG)

        print("~~ TARGET ADDRESSES: ~~")
        for addr in self.target_addrs:
            print(f"\t- 0x{addr:08x}")

        print("About to vscale_dma")
        # DMA Channels
        self.row_addr = DMA()               # 2. Vertical / row control (read and write)
        self.row_addr_target = DMA()        # 3. Uses ring buffer to tell row_addr where to write its address to
        self.color_lookup = DMA()           # 4. Palette color lookup / transfer
        self.px_read_dma = DMA()            # 5. Sprite data
        self.px_write_dma = DMA()           # 6. Display output
        self.h_scale = DMA()                # 7. Horizontal scale pattern

        self.palette_addr = None

        print("About to start sm_pixel_scaler")
        # PIO1 setup (#4 is SM #1 on PIO1)
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=5_000_000,
        )
        # PIO1 SM #2
        self.sm_read_addr = StateMachine(
            5, read_addr,
            freq=5_000_000,
        )
        self.init_patterns()
        self.init_dma()

    def feed_address_pair(self):
        # Update both accumulators in one go using BASE_1AND0 register
        # Lower 16 bits go to BASE0, upper bits to BASE1
        # mem32[INTERP0_BASE_1AND0] = 0x00010001  # Increment both accumulators by 1

        # Get both results with one register access each
        # This is more efficient and ensures better synchronization

        new_write = mem32[INTERP0_POP_FULL]
        new_read = mem32[INTERP1_POP_FULL]

        """ check bounds """
        # if new_write > self.max_write_addr:
        #     return False

        if self.debug_interp_list:
            print(f"ADDR PAIR:")
            print(f"\t W:0x{new_write:08X}")
            print(f"\t R:0x{new_read:08X}")

        self.sm_read_addr.put(new_write)
        self.sm_read_addr.put(new_read)

        return True

    def draw_sprite(self, meta:SpriteType, x, y, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """
        self.reset()

        # h_scale = 1.0
        # v_scale = 1.0

        prof.start_profile('scaler.scaled_width_height')
        scaled_height = int(meta.height * v_scale)
        self.scaled_height = scaled_height
        self.read_finished = False
        prof.end_profile('scaler.scaled_width_height')

        # Set up base addresses
        base_read = addressof(image.pixel_bytes)
        base_write = int(self.display.write_addr + (y * self.display.width * 2) + (x * 2))

        if self.debug_dma:
            print(f"Drawing a sprite of SCALED {meta.width}x{meta.height} @ base addr 0x{base_write:08X}")

        """ Config interpolator """
        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(base_read, base_write, scaled_height, v_scale)
        prof.end_profile('scaler.init_interp_sprite')

        prof.start_profile('scaler.init_pio')
        palette_addr = addressof(image.palette_bytes)
        self.init_pio(palette_addr)
        self.palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.init_dma_sprite(meta.height, meta.width, h_scale)
        prof.end_profile('scaler.init_dma_sprite')

        if self.debug_dma:
            self.dbg.debug_pio_status(sm0=True, sm1=True)

        if self.debug_dma:
            """ Show key addresses """

            print()
            print("~~ KEY MEMORY ADDRESSES ~~")
            print(f"    ADDRS VALUE ADDR:          0x{addressof(self.value_addrs):08X}")
            print(f"    TARGET ADDRS ADDR:         0x{addressof(self.target_addrs):08X}")
            print(f"    PALETTE ADDR:              0x{self.palette_addr:08X}")
            print(f"    SPRITE READ BASE ADDR:     0x{base_read:08X}")
            print(f"    DISPLAY WRITE BASE ADDR:   0x{base_write:08X}")
            print()

        """ Start DMA chains and State Machines """
        self.start(scaled_height)


    def debug_dma_and_pio(self):
        self.dbg.debug_dma(self.row_addr, "row address", "row_addr", 2)
        self.dbg.debug_dma(self.row_addr_target, "row address target", "row_addr_target", 3)
        self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
        self.dbg.debug_dma(self.px_read_dma, "pixel read", "pixel_read", 5)
        self.dbg.debug_dma(self.px_write_dma, "pixel write", "pixel_write", 6)
        self.dbg.debug_dma(self.h_scale, "horiz_scale", "horiz_scale", 7)

        self.dbg.debug_pio_status(sm0=True, sm1=True)

    def start(self, scaled_height):
        """ START: Color lookup must be activated too, since it is right after a SM, so there's no direct way to trigger it"""

        self.addr_counter = 0

        self.sm_read_palette.active(1)
        self.sm_read_addr.active(1)

        self.row_addr_target.active(1)
        self.color_lookup.active(1)
        self.h_scale.active(1)

        self.feed_address_pair() # We need to send the first one to kick things off

        while not self.read_finished:
            if self.debug_dma:
                print("\n~~ DMA CHANNELS in start loop ~~~~~~~~~~~\n")
                self.debug_dma_and_pio()
                print()

        if self.debug_with_debug_bytes:
            self.dbg.print_debug_bytes(self.debug_bytes1)

    def finish(self):
        self.read_finished = True
        self.rows_read_count = 0

        if self.debug:
            print("<<<< SPRITE FINISHED >>>>")

    def init_interp_sprite(self, read_base, write_base, sprite_height, scale_y_one = 1.0):
        self.scaled_height = sprite_height
        FRAC_BITS = 5 # Use x.y fixed point
        INT_BITS = 32 - FRAC_BITS
        BASE_SCALE = 16 # The scale's "base"

        """
        scale_y = 1 # 500%
        scale_y = 2 # 400%
        scale_y = 4 # 400%
        scale_y = 8 # 200%
        scale_y = 16 # 100% <
        scale_y = 32 # 50%
        scale_y = 64 # 25%
        """

        scale_y = BASE_SCALE / scale_y_one

        # Calculate scaling values
        read_step = int((scale_y) * (1 << FRAC_BITS))  # Convert step to fixed point
        int_bits_str = '^'*INT_BITS
        frac_bits_str = '`'*FRAC_BITS
        if self.debug_interp:
            print(f"* INTERP SPRITE:")
            print(f"\t write_base:      0x{write_base:08X}")
            print(f"\t read_base:       0x{read_base:08X}")
            print(f"\t scale_y:         {scale_y}")
            print(f"\t scale_y_perct:     {int(scale_y*100)}%")
            print(f"\t step:            0x{read_step:08X}")
            print(f"\t step b.:         {read_step:>032b}")
            print(f"\t int/frac bits:   {int_bits_str}{frac_bits_str}")

        # INTERP0: Write address generation (display)
        write_ctrl_config = (
                (0 << 0) |  # No shift needed for write addresses
                (0 << 5) |  # No mask needed
                (31 << 10) |  # Full 32-bit mask
                (0 << 15)  # No sign
        )
        # For write addresses we want: BASE0 + ACCUM0
        mem32[INTERP0_BASE0] = 0  # Base address component
        mem32[INTERP0_BASE1] = self.display_stride  # Row increment. Increasing beyond stride can be used to skew sprites.
        mem32[INTERP0_ACCUM0] = write_base  # Starting address
        mem32[INTERP0_CTRL_LANE0] = write_ctrl_config
        mem32[INTERP0_CTRL_LANE1] = write_ctrl_config

        # INTERP1: Read address generation with scaling
        read_ctrl_lane0 = (
                (0 << 0) |  # No shift on accumulator/raw value
                ((FRAC_BITS) << 10) | # mask full (MSB)
                (0 << 15) | # No sign extension
                (1 << 16) | # CROSS_INPUT - also add ACCUM1
                (1 << 18) |  # ADD_RAW - Enable raw accumulator addition
                (1 << 20)  # CROSS_RESULT - Use other lane's result
        )

        # Lane 1 config - handles integer extraction
        read_ctrl_lane1 = (
                (FRAC_BITS << 0) |  # Shift right to get integer portion
                (FRAC_BITS << 5) |  # Start mask at bit 0
                (INT_BITS << 10) |  # Full 32-bit mask to preserve address
                (0 << 15) | # No sign extension
                (1 << 18)   # ADD_RAW - Enable raw accumulator addition
        )

        # Configure remaining variables
        mem32[INTERP1_BASE0] = 0  # # Row increment in fixed point
        mem32[INTERP1_BASE1] = read_step
        mem32[INTERP1_BASE2] = read_base # Base sprite read address
        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

        mem32[INTERP1_CTRL_LANE0] = read_ctrl_lane0
        mem32[INTERP1_CTRL_LANE1] = read_ctrl_lane1

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

        """ CH:2 Row address control DMA """
        row_addr_ctrl = self.row_addr.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=False,  # Reads from FIFO
            inc_write=False,  # Fixed write target
            treq_sel=DREQ_PIO1_RX1
        )

        self.row_addr.config(
            count=1,
            read=PIO1_RX1,
            ctrl=row_addr_ctrl
        )

        """ CH:3 Row address target DMA """
        row_addr_target_ctrl = self.row_addr_target.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=True,      # Through control blocks
            inc_write=False,    # always write to DMA2 WRITE
            ring_sel=0,         # ring on read channel (read/write TARGET address)
            ring_size=3,        # 2^3 or 8 bytes for 2 addresses in ring buffer to loop through (read & write)
            chain_to=self.color_lookup.channel,
            treq_sel=DREQ_PIO1_RX1, # Crucial for sync'ing with row_addr
        )

        self.row_addr_target.config(
            count=2, # We are sending 1 addr to a READ reg, and 1 to a WRITE reg
            read=addressof(self.target_addrs),          # read/write TARGET address block array
            write=ROW_ADDR_DMA_BASE + DMA_WRITE_ADDR_TRIG,
            ctrl=row_addr_target_ctrl,
        )

        """ CH:5. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read_dma.pack_ctrl(
            size=2,
            inc_read=True,      # Through sprite data
            inc_write=False,    # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO1_TX0,
            bswap=True,
            irq_quiet=False
        )

        self.px_read_dma.config(
            count=1,
            read=0,  # To be Set per row
            write=PIO1_TX0,
            ctrl=px_read_ctrl
        )

        """ CH:4 Color lookup DMA """
        color_lookup_ctrl = self.color_lookup.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses
            inc_read=False,
            inc_write=False,  # always writes to DMA WRITE
            irq_quiet=False,
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.row_addr_target.channel,
        )

        self.color_lookup.config(
            count=1, # TBD
            read=PIO1_RX0,  # read/write TARGET address block array
            write=WRITE_DMA_BASE + DMA_READ_ADDR,
            ctrl=color_lookup_ctrl
        )
        self.color_lookup.irq(handler=self.irq_color_lookup)

        """ CH:6. Display write DMA --------------------------- """
        px_write_ctrl = self.px_write_dma.pack_ctrl(
            size=1, # 16 bit pixels
            inc_read=False,  # from PIO
            inc_write=True,  # Through display
            chain_to=self.h_scale.channel,
        )

        self.px_write_dma.config(
            count=1,
            write=0, # TBD
            ctrl=px_write_ctrl
        )

        print(f"Write DMA initial write addr: 0x{self.px_write_dma.write:08x}")

        """ CH:7. Horiz. scale DMA --------------------------- """
        h_scale_ctrl = self.h_scale.pack_ctrl(
            size=2,
            treq_sel=DREQ_PIO1_RX0,
            inc_read=True,
            inc_write=False,
            ring_sel=False,  # ring on read
            ring_size=4,    # n bytes = 2^n
            irq_quiet=False,
            # chain_to=self.px_write_dma.channel  # Add this to make it cycle
        )

        self.h_scale.config(
            count=0, # TBD
            # read=xxx,  # Current horizontal pattern (to be set later)
            write=WRITE_DMA_BASE + DMA_TRANS_COUNT_TRIG,
            ctrl=h_scale_ctrl
        )
        self.h_scale.irq(handler=self.irq_hscale)

        if self.debug_dma:
            print("~~ DMA CHANNELS in INIT_DMA ~~~~~~~~~~~")
            self.debug_dma_and_pio()

    def init_dma_sprite(self, height, width, h_scale=1.0):
        """ Sprite-specific DMA configuration goes here """

        h_pattern_arr = self.h_patterns[h_scale]
        self.h_scale.read = addressof(h_pattern_arr)  # Make sure we're using the address
        self.h_scale.count = width
        # self.h_scale.count = 0
        self.color_lookup.count = width

        px_per_tx = PX_READ_BYTE_SIZE * 2
        tx_per_row = math.ceil(width / px_per_tx)
        self.px_read_dma.count = tx_per_row

        prof.start_profile('scaler.h_pattern')
        h_pattern_arr = self.h_patterns[h_scale]
        self.h_scale.read = h_pattern_arr
        prof.end_profile('scaler.h_pattern')

        if self.debug_dma:
            print("DMA CONFIG'D for: ")
            print(f"\t h_scale = {h_scale}")
            print(f"\t height / width = {height} / {width}")
            print(f"\t px_per_tx = {px_per_tx}")
            print(f"\t tx_per_row = {tx_per_row}")
            print(f"\t count - px_read_dma: {self.px_read_dma.count}")
            print(f"\t count - color_lookup: {self.color_lookup.count}")
            print(f"\t h_scale addr:        0x{addressof(h_pattern_arr):08X}")

            print()
            print("~~ DMA AFTER SPRITE CONFIG ~~~~~~~")
            self.debug_dma_and_pio()
    def init_patterns(self):
        """Initialize horizontal scaling patterns"""
        # Base patterns for different scaling factors
        raw_patterns = {
            0.125:  [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5%
            0.250:  [0, 0, 1, 0, 0, 0, 1, 0],  # 25%
            0.375:  [0, 0, 1, 0, 0, 1, 0, 1],  # 37.5%
            0.500:  [0, 1, 0, 1, 0, 1, 0, 1],  # 50% scaling - oddly only works if you start with zero
            0.625:  [0, 1, 1, 0, 1, 0, 1, 1],  # 62.5%
            0.750:  [0, 1, 1, 1, 0, 1, 1, 1],  # 75% - works
            0.875:  [1, 1, 1, 1, 0, 1, 1, 1],  # 87.5%
            1.0:    [1, 1, 1, 1, 1, 1, 1, 1],  # No scaling
            1.5:    [1, 2, 1, 2, 1, 2, 1, 2],  # 1.5x scaling
            2.0:    [2, 2, 2, 2, 2, 2, 2, 2],  # 2x scaling
            3.0:    [3, 3, 3, 3, 3, 3, 3, 3],  # 3x scaling
            4.0:    [4, 4, 4, 4, 4, 4, 4, 4],  # 4x scaling
            8.0:    [8, 8, 8, 8, 8, 8, 8, 8],  # 8x scaling
            16.0:   [16, 16, 16, 16, 16, 16, 16, 16],  # 8x scaling
        }

        for i, (key, val)  in enumerate(raw_patterns.items()):
            print(f"{key} for {val}")
            array_pattern = self.create_aligned_pattern(val)
            self.h_patterns[key] = array_pattern

        # Calculate pattern sums for DMA transfer counts
        # self.h_pattern_sums = {
        #     scale: sum(pattern) for scale, pattern in self.h_patterns.items()
        # }

    def create_aligned_pattern(self, list):
        # Create aligned array for scaling patterns
        arr_buff = aligned_buffer(8 * 4, alignment=4)
        final_array = array('L', arr_buff)

        for i in range(8):
            final_array[i] = list[i]

        return final_array

    def reset(self):
        """Clean up / close resources"""
        self.row_addr_target.active(0)
        self.row_addr.active(0)
        self.px_read_dma.active(0)
        self.h_scale.active(0)
        self.sm_read_palette.active(0)
        self.sm_read_addr.active(0)
        self.px_write_dma.active(0)
        self.color_lookup.active(0)

        self.rows_read_count = 0

        # Clear interpolator accumulators
        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0

        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

    def init_pio(self, palette_addr):
        self.sm_read_addr.restart()
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)

    def irq_hscale(self, ch):
        """ Every time the color lookup Channel finishes (a whole rows worth of lookups), we add +1 to the number
                of rows read (should probably be rows written). Is there a better way without CPU involvement? """

        if self.debug:
            print(f"*** HSCALE IRQ TRIGGERED - rows:{self.rows_read_count}/{self.scaled_height} ***")

        # if self.rows_read_count < self.scaled_height:
        #     res = self.feed_address_pair()
        #     if not res:
        #         self.finish()
        # else:
        #     self.finish()

    def irq_color_lookup(self, ch):
        """ This IRQ is called with the color_lookup DMA channel finishes all of its transactions. In order to work, the
        tx count needs to be set to the sprite width"""
        self.rows_read_count += 1

        if self.rows_read_count < self.scaled_height:
            res = self.feed_address_pair()
            if not res:
                self.finish()
        else:
            self.finish()

        if self.debug:
            print(f"!!! COLOR LOOKUP IRQ - rows read: {self.rows_read_count}!!!")

