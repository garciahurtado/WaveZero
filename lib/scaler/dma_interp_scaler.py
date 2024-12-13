import time

import math

from itertools import chain

from _rp2 import DMA, StateMachine
from uarray import array
from uctypes import addressof

from images.image_loader import ImageLoader
from images.indexed_image import Image
from scaler.dma_scaler_const import *
from scaler.dma_scaler_pio import read_palette
from scaler.dma_scaling_patterns import ScalingPatterns
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

PX_READ_BYTE_SIZE = 2

class SpriteScaler():
    rows_finished = False

    def __init__(self, display):
        self.display = display
        self.read_blocks = []
        self.write_blocks = None
        self.value_addrs = []

        self.dbg = ScalerDebugger()
        self.debug_bytes1 = self.dbg.get_debug_bytes(byte_size=0, count=16, aligned=True)
        self.debug_bytes2 = self.dbg.get_debug_bytes(byte_size=0, count=16, aligned=True)
        self.debug_dma = False
        self.debug = True
        self.debug_interp = True

        self.display_stride = self.display.width * 2

        """" Add two blocks, one for the pixel reader READ addr, and one for the pixel writer WRITE addr """

        # target_addrs_buf = aligned_buffer(2, alignment=8)
        self.target_addrs = array('L', [0]*2)

        # Write addr, then read addr + trigger
        self.target_addrs[0] = int(DMA_BASE_6 + DMA_WRITE_ADDR)
        self.target_addrs[1] = int(DMA_BASE_5 + DMA_READ_ADDR_TRIG)

        print("~~ TARGET ADDRESSES: ~~")
        for addr in self.target_addrs:
            print(f"\t- 0x{addr:08x}")

        # patterns = ScalingPatterns()
        # self.h_patterns = patterns.h_patterns_int
        # self.v_patterns_up = patterns.v_patterns_up_int
        # self.v_patterns_down = patterns.v_patterns_down_int
        # print("About to init_patterns")
        # self.init_patterns()

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
        # PIO setup (SM ID 4 is #1 on PIO1)
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=120_000_000,
        )
        self.init_vertical_patterns()
        self.init_dma()

    def draw_sprite(self, meta:SpriteType, x, y, image:Image, scale_x=1.0, scale_y=1.0):
        """Draw a scaled sprite at the specified position"""

        prof.start_profile('scaler.scaled_width_height')
        scaled_width = int(meta.width * scale_x)
        scaled_height = int(meta.height * scale_y)
        prof.end_profile('scaler.scaled_width_height')

        # Set up vertical control blocks
        base_read = addressof(image.pixel_bytes)
        base_write = int(self.display.write_addr + ((y * self.display.width) + x) * 2)

        if self.debug:
            print(f"Drawing a sprite of SCALED {scaled_width}x{scaled_height} @ base addr 0x{base_write:08X}")
            print(f"(ROWS finished: {self.rows_finished})")

        prof.start_profile('scaler.init_v_ctrl_blocks')
        self.init_v_ctrl_blocks(
            meta=meta,
            scale_y=scale_y,
            scaled_height=scaled_height,
            scaled_width=scaled_width,
            base_read_addr=base_read,
            base_write_addr=base_write
        )
        prof.end_profile('scaler.init_v_ctrl_blocks')

        prof.start_profile('scaler.init_pio')
        palette_addr = addressof(image.palette_bytes)
        self.init_pio(palette_addr)
        self.palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        if self.debug_dma:
            print(f"About to Init DMA w/ w/h: {meta.width}x{meta.height} /// scaled_height: {scaled_height} / scaled_width: {scaled_width}")

        prof.start_profile('scaler.init_dma_sprite')
        self.init_dma_sprite(scaled_height, scaled_width)
        prof.end_profile('scaler.init_dma_sprite')

        if self.debug_dma:
            self.dbg.debug_pio_status(sm0=True)

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

        """ START: Color lookup must be activated too, since it is right after a SM, so there's no direct way to trigger it"""
        self.row_addr_target.active(1)
        self.color_lookup.active(1)
        self.sm_read_palette.active(1)

        if self.debug_dma:
            print("\n~~ DMA CHANNELS AFTER ~~~~~~~~~~~\n")
            self.dbg.debug_dma(self.row_addr, "row address", "row_addr", 2)
            self.dbg.debug_dma(self.row_addr_target, "row address target", "row_addr_target", 3)
            self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
            self.dbg.debug_dma(self.px_read_dma, "pixel read", "pixel_read", 5)
            self.dbg.debug_dma(self.px_write_dma, "pixel write", "pixel_write", 6)

            self.dbg.debug_pio_status(sm0=True)
            print()

    def init_vertical_patterns(self):
        """Similar to horizontal patterns but for row repeats"""
        v_patterns = {
            # Upscaling
            4.0: [4, 4, 4, 4, 4, 4, 4, 4],  # 400%
            3.0: [3, 3, 3, 3, 3, 3, 3, 3],  # 300%
            2.0: [2, 2, 2, 2, 2, 2, 2, 2],  # 200%
            1.5: [2, 1, 2, 1, 2, 1, 2, 1],  # Alternating double/single = 150%

            # No scaling
            1.0: [1, 1, 1, 1, 1, 1, 1, 1],  # One-to-one mapping

            # Downscaling
            0.75: [1, 1, 1, 0, 1, 1, 1, 0],  # Take 3 skip 1 = 75%
            0.5: [1, 0, 1, 0, 1, 0, 1, 0],  # Skip every other = 50%
            0.33: [1, 0, 0, 1, 0, 0, 1, 0],  # Every third row ≈ 33%
            0.25: [1, 0, 0, 0, 1, 0, 0, 0],  # Every fourth row = 25%
        }

        # v_patterns = {
        #     0.5: [1, 1, 2, 1, 1, 2, 1, 2],  # Skip rows
        #     1.0: [1, 1, 1, 1, 1, 1, 1, 1],  # Normal
        #     2.0: [2, 2, 2, 2, 2, 2, 2, 2],  # Double rows
        #     3.0: [3, 3, 3, 3, 3, 3, 3, 3],  # Triple rows
        #     # ... others from the pattern list
        # }
        self.v_patterns = {scale: array('I', pattern) for scale, pattern in v_patterns.items()}

        return True

    def init_v_ctrl_blocks(self, meta:SpriteType, scale_y, scaled_height, scaled_width, base_read_addr, base_write_addr):
        """Create control blocks for vertical scaling"""
        """ @todo: init address calculations using interp, to speed things up """

        """ Testing Upscale / downscale ratios """
        if self.debug:
            print(f"Sprite HEIGHT = {scaled_height} / num addr blocks: {scaled_height*2}")

        """ Config interpolator """
        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(base_read_addr, base_write_addr, scaled_width)
        prof.end_profile('scaler.init_interp_sprite')

        """ Test self.init_interp_sprite() """

        prof.start_profile('scaler.create_address_array')
        # Create array first
        self.value_addrs = self.create_address_array(scaled_height)
        prof.end_profile('scaler.create_address_array')

        prof.start_profile('scaler.fill_address_list')
        # Fill it using viper function
        self.fill_address_list(
            addressof(self.value_addrs),  # Pass raw addresses as integers
            INTERP0_PEEK_LANE0,
            INTERP0_POP_LANE1,
            scaled_height
        )
        prof.end_profile('scaler.fill_address_list')


        if self.debug_interp:
            i = 0
            print("INTERP WRITE ADDR LIST")
            print("----------------------")
            while i < len(self.value_addrs)-1:
                print(f"0x{self.value_addrs[i]:08x}")
                i += 2

            i = 0
            print("INTERP READ ADDR LIST")
            print("----------------------")
            while i < len(self.value_addrs)-1:
                print(f"0x{self.value_addrs[i+1]:08x}")
                i += 2

        prof.start_profile('scaler.convert_to_array')
        self.value_addrs = array('L', self.value_addrs)
        prof.end_profile('scaler.convert_to_array')

        return True

        """
        DEBUGGING
        """

        """ "value_addrs" contain the addresses that will be written to the destination,
        and "target_addrs" the addresses to which these values will be written (ie: the read and write DMAs) """

        y_pos = 0
        row_width_4bit = math.ceil(meta.width / 2)
        value_addrs = []
        write_row_id = 0
        read_row_id = 0

        for row_count in range(0, meta.height):
            # Source sprite reading address
            count = v_pattern[row_count % 8]  # Apply vertical scaling pattern, which repeats every 8 items

            """ Needed for downscaling. For every 0 in the scaling pattern, we increase the read row ID one extra time,
            therefore skipping one source row"""

            read_addr = base_read_addr + (read_row_id * (row_width_4bit))

            """ For vertical upscaling, we repeat the source row 0-x times """
            for rep in range(count):
                # Display writing address
                write_addr = base_write_addr + (write_row_id * self.display_stride)

                # print(f" R/W {read_addr:08X} / {write_addr:08X}")
                value_addrs.append(write_addr)        # 1st for the writer
                value_addrs.append(read_addr)       # 2nd for the reader
                write_row_id += 1

            read_row_id += 1

        """ Add a final tuple of blank addresses, to trigger the null IRQ on the channel """
        value_addrs.append(0x00000000)
        value_addrs.append(0x00000000)
        self.value_addrs = array('L', value_addrs)

        if self.debug_dma:
            """ DEBUG array """
            print(f"\nVALUE ADDRS ({len(self.value_addrs)}): ")
            for i, addr in enumerate(self.value_addrs):
                print(f"  #{i}: 0x{addr:08x}")

            print("POINTERS -----------")
            print(f"  VALUE ADDR PTR: 0x{addressof(self.value_addrs):08X}")
            print(f"  TARGET ADDR PTR: 0x{addressof(self.target_addrs):08X}")

            print(f"TARGET ADDRS --------")
            for addr in self.target_addrs:
                print(f"  ADDR: 0x{addr:08X}")


    def init_interp_sprite(self, read_base, write_base, sprite_width):
        row_width_4bit = math.ceil(sprite_width / 2)

        RW_BASE = 0x20010000 # this is the base address for all read (Sprite) and write (display) addresses
        read_offset = read_base - RW_BASE
        write_offset = write_base - RW_BASE

        if self.debug_interp:
            print(f"* INTERP SPRITE:")
            print(f"\t row_width: {row_width_4bit}")
            print(f"\t write_base: 0x{write_base:08X}")
            print(f"\t write_offset: 0x{write_offset:08X}")
            print(f"\t read_base: 0x{read_base:08X}")
            print(f"\t read_offset: 0x{read_offset:08X}")

        # Remaining interp config

        # Common control config for address generation
        ctrl_config = (
                (0 << 0) |  # No shift
                (0 << 5) |  # Mask LSB = 0
                (31 << 10) |  # Full 32-bit mask
                (0 << 15)   # FORCE_MSB = 0
                # (1 << 17)   # ADD_RAW enabled
        )

        # INTERP0 for write addresses (display)
        # mem32[INTERP0_BASE0] = write_base  # Base addr
        mem32[INTERP0_BASE0] = self.display_stride  # write step
        mem32[INTERP0_BASE1] = row_width_4bit       # read step
        mem32[INTERP0_BASE2] = 0

        # We use ACCUM0 for the WRITE initial address offset and ACCUM1 for the READ
        # Substract one interval from the base addr, to avoid skipping 1st row
        mem32[INTERP0_ACCUM0] = write_base - self.display_stride
        mem32[INTERP0_ACCUM1] = read_base - row_width_4bit

        mem32[INTERP0_CTRL_LANE0] = ctrl_config
        mem32[INTERP0_CTRL_LANE1] = ctrl_config

        if self.debug_interp:
            print("Initial config:")
            print("INTERP0 (ALL addresses):")
            print(f"  BASE0: 0x{mem32[INTERP0_BASE0]:08x}")
            print(f"  BASE1: 0x{mem32[INTERP0_BASE1]:08x}")
            print(f"  BASE2: 0x{mem32[INTERP0_BASE2]:08x}")
            print(f"  ACCU0: 0x{mem32[INTERP0_ACCUM0]:08x}")
            print(f"  ACCU1: 0x{mem32[INTERP0_ACCUM1]:08x}")


    def create_address_array(self, size: int) -> array:
        total_size = size * 2 + 1
        return array('L', [0] * total_size)

    @micropython.viper
    def fill_address_list(self, arr_ptr: ptr32, write_base_reg: ptr32, read_base_reg: ptr32, size: int):
        idx = 0
        while idx < size:
            write_addr = ptr32(write_base_reg)[0]  # Reads from POP registers
            read_addr = ptr32(read_base_reg)[0]

            arr_ptr[idx * 2] = write_addr
            arr_ptr[idx * 2 + 1] = read_addr
            idx += 1

        # Add null terminator
        arr_ptr[size * 2] = 0

    def init_dma(self):
        """Set up the complete DMA chain for sprite scaling"""

        """ CH:2 Row address control DMA """
        row_addr_ctrl = self.row_addr.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=True,  # Through control blocks
            inc_write=False,  # Fixed write target
            irq_quiet=0
        )

        self.row_addr.config(
            count=1,
            ctrl=row_addr_ctrl
        )
        self.row_addr.irq(handler=irq_rows_end)

        """ CH:3 Row address target DMA """
        row_addr_target_ctrl = self.row_addr_target.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=True,      # Through control blocks
            inc_write=False,    # always write to DMA2 WRITE
            ring_sel=0,         # ring on read channel (read/write TARGET address)
            ring_size=3,        # 2^3 or 8 bytes for 2 addresses in ring buffer to loop through (read & write)
            chain_to=self.color_lookup.channel,
            treq_sel=DREQ_TIMER_1,
        )

        self.row_addr_target.config(
            count=2, # We are sending 1 addr to a READ reg, and 1 to a WRITE reg
            read=self.target_addrs,          # read/write TARGET address block array
            write=ROW_ADDR_DMA_BASE + DMA_WRITE_ADDR_TRIG,
            ctrl=row_addr_target_ctrl,
        )

        """ CH:4 Color lookup DMA """
        color_lookup_ctrl = self.color_lookup.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses
            inc_read=False,
            inc_write=False,  # always writes to DMA WRITE
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.row_addr_target.channel,
        )

        self.color_lookup.config(
            count=0, # TBD
            read=PIO1_RX0,  # read/write TARGET address block array
            write=WRITE_DMA_BASE + DMA_READ_ADDR_TRIG,
            ctrl=color_lookup_ctrl
        )

        """ CH:5. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read_dma.pack_ctrl(
            size=PX_READ_BYTE_SIZE,
            inc_read=True,      # Through sprite data
            inc_write=False,    # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO1_TX0,
            bswap=True
        )

        # tx_per_row = (width + 1) // 2  # Round up for 4-bit pixels
        # print(f"tx_per_row: {tx_per_row}")

        self.px_read_dma.config(
            count=0,
            read=0,  # To be Set per row
            write=PIO1_TX0,
            ctrl=px_read_ctrl
        )
        # self.px_read_dma.irq(self.irq_end_row, hard=True)

        """ CH:6. Display write DMA --------------------------- """
        # px_write_count = math.ceil(width / 4)
        px_write_ctrl = self.px_write_dma.pack_ctrl(
            size=1, # 16 bit pixels
            inc_read=False,  # from PIO
            inc_write=True,  # Through display
        )

        self.px_write_dma.config(
            count=1,
            write=0, # TBD
            ctrl=px_write_ctrl
        )

        """ CH:6. Horiz. scale DMA --------------------------- """
        # hscale_dma_ctrl = self.hscale_dma.pack_ctrl(
        #     size=2,
        #     inc_read=True,
        #     inc_write=True,
        #     ring_sel=1,
        #     ring_size=3,  # 8 entries = 2^3
        #     chain_to=self.px_read_dma.channel
        # )
        #
        # self.hscale_dma.config(
        #     count=8,  # 8-entry patterns
        #     # read=None,  # Current horizontal pattern (to be set later)
        #     # write=WRITE_DMA_BASE + DMA_TRANS_COUNT_TRIG,
        #
        #     ctrl=hscale_dma_ctrl
        # )

        if self.debug_dma:
            self.dbg.debug_dma(self.row_addr, "row address", "row_addr", 2)
            self.dbg.debug_dma(self.row_addr_target, "row address target", "row_addr_target", 3)
            self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
            self.dbg.debug_dma(self.px_read_dma, "pixel read", "pixel_read", 5)
            self.dbg.debug_dma(self.px_write_dma, "pixel write", "pixel_write", 6)
            self.dbg.debug_pio_status(sm0=True)

    def irq_rows_end(self):
        self.rows_finished = True

    def init_dma_sprite(self, scaled_height, scaled_width):
        """ Sprite-specific DMA configuration goes here """

        self.row_addr.config(read=self.value_addrs)
        px_per_tx = 2 * (PX_READ_BYTE_SIZE*2)

        self.px_read_dma.config(count=scaled_width//px_per_tx)
        self.px_write_dma.config(count=1)
        self.color_lookup.config(count=scaled_width)

    def init_patterns(self):
        """Initialize horizontal scaling patterns"""
        # Base patterns for different scaling factors
        self.h_patterns = {
            0.5: array('B', [1, 0, 1, 0, 1, 0, 1, 0]),  # 50% scaling
            1.0: array('B', [1, 1, 1, 1, 1, 1, 1, 1]),  # No scaling
            2.0: array('B', [2, 2, 2, 2, 2, 2, 2, 2]),  # 2x scaling
            3.0: array('B', [3, 3, 3, 3, 3, 3, 3, 3]),  # 3x scaling
        }

        # Calculate pattern sums for DMA transfer counts
        self.h_pattern_sums = {
            scale: sum(pattern) for scale, pattern in self.h_patterns.items()
        }

    def reset(self):
        """Clean up / close resources"""
        self.row_addr_target.active(0)
        self.row_addr.active(0)
        self.px_read_dma.active(0)
        self.h_scale.active(0)
        self.sm_read_palette.active(0)
        self.px_write_dma.active(0)
        self.color_lookup.active(0)

        # First, disable any ongoing interpolator operations by clearing control registers
        mem32[INTERP0_CTRL_LANE0] = 0
        mem32[INTERP0_CTRL_LANE1] = 0

        mem32[INTERP1_CTRL_LANE0] = 0
        mem32[INTERP1_CTRL_LANE1] = 0

        # Reset all interp accumulators
        mem32[INTERP0_BASE0] = 0
        mem32[INTERP0_BASE1] = 0
        mem32[INTERP0_BASE2] = 0

        mem32[INTERP1_BASE0] = 0
        mem32[INTERP1_BASE1] = 0
        mem32[INTERP1_BASE2] = 0

        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0

        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

        if self.debug_interp:
            # Read initial values to verify reset
            print(f"Initial ACCUM0: 0x{mem32[INTERP0_ACCUM0]:08X}")
            print(f"Initial ACCUM1: 0x{mem32[INTERP0_ACCUM1]:08X}")

    def init_pio(self, palette_addr):
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)

    def init_ref_palette(self):
        img_name = '/img/scaler_test_pattern.bmp'
        ref_img = ImageLoader.load_image(img_name, 4, 4)
        palette_addr = addressof(ref_img.palette_bytes)
        print(f"   * PALETTE ADDR CALCULATED AS: 0x{palette_addr:08X}")
        self.palette_addr = palette_addr

        pass

def irq_rows_end(irq):
    SpriteScaler.rows_finished = True
