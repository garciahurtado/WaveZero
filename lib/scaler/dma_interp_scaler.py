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

ROW_ADDR_DMA_BASE = DMA_BASE_2
ROW_ADDR_TARGET_DMA_BASE = DMA_BASE_3
COLOR_LOOKUP_DMA_BASE = DMA_BASE_4
READ_DMA_BASE = DMA_BASE_5
WRITE_DMA_BASE = DMA_BASE_6
HSCALE_DMA_BASE = DMA_BASE_7

PX_READ_BYTE_SIZE = 4 # Bytes per word in the pixel reader

class SpriteScaler():
    rows_finished = False

    def __init__(self, display):
        self.display = display
        self.read_blocks = []
        self.write_blocks = None

        """ Create array with maximum possible number of addresses """
        self.value_addrs = array('L', [0] * (display.height * 2))
        self.value_addr_ptr = None
        self.rows_read_count = 0

        self.dbg = ScalerDebugger()
        self.debug_bytes1 = self.dbg.get_debug_bytes(byte_size=0, count=32)
        self.debug_bytes2 = self.dbg.get_debug_bytes(byte_size=0, count=32)
        self.debug_dma = False
        self.debug = False
        self.debug_interp = False
        self.debug_interp_list = False
        self.debug_with_debug_bytes = False

        self.display_stride = self.display.width * 2

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
            freq=10_000_000,
        )
        # PIO1 SM #2
        self.sm_read_addr = StateMachine(
            5, read_addr,
            freq=10_000_000,
        )
        # self.sm_read_addr.irq(handler=self.read_addr_irq)
        self.init_vertical_patterns()
        self.init_dma()


    def feed_address_pair(self):
        new_read = mem32[INTERP0_PEEK_LANE0]
        new_write = mem32[INTERP0_POP_LANE1]

        print(f"#{self.addr_counter} ADDR PAIR:")
        if self.debug_interp_list:
            print(f"\t W:0x{new_write:08X}")
            print(f"\t R:0x{new_read:08X}")

        self.sm_read_addr.put(new_read)  # read addr
        self.sm_read_addr.put(new_write)  # write addr

        self.addr_counter += 1

    def draw_sprite(self, meta:SpriteType, x, y, image:Image, scale_x=1.0, scale_y=1.0):
        """Draw a scaled sprite at the specified position"""

        prof.start_profile('scaler.scaled_width_height')
        scaled_width = int(meta.width * scale_x)
        scaled_height = int(meta.height * scale_y)
        prof.end_profile('scaler.scaled_width_height')

        # Set up vertical control blocks
        base_read = addressof(image.pixel_bytes)
        base_write = int(self.display.write_addr + (y * self.display.width * 2) + (x * 2))

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

        if self.debug_dma:
            print("\n~~ DMA CHANNELS AFTER ~~~~~~~~~~~\n")
            self.dbg.debug_dma(self.row_addr, "row address", "row_addr", 2)
            self.dbg.debug_dma(self.row_addr_target, "row address target", "row_addr_target", 3)
            self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
            self.dbg.debug_dma(self.px_read_dma, "pixel read", "pixel_read", 5)
            self.dbg.debug_dma(self.px_write_dma, "pixel write", "pixel_write", 6)

            self.dbg.debug_pio_status(sm0=True, sm1=True)
            print()

        print("___ END OF SPRITE DRAW ___")

    def start(self, scaled_height):
        """ START: Color lookup must be activated too, since it is right after a SM, so there's no direct way to trigger it"""

        self.addr_counter = 0

        self.row_addr_target.active(1)
        self.color_lookup.active(1)
        self.sm_read_palette.active(1)
        self.sm_read_addr.active(1)

        # self.feed_address_pair() # We need to send the first one to kick things off

        while self.rows_read_count <= scaled_height:
            self.feed_address_pair()

            if self.debug_dma:
                print("\n~~ DMA CHANNELS AFTER ~~~~~~~~~~~\n")
                self.dbg.debug_dma(self.row_addr, "row address", "row_addr", 2)
                self.dbg.debug_dma(self.row_addr_target, "row address target", "row_addr_target", 3)
                self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
                self.dbg.debug_dma(self.px_read_dma, "pixel read", "pixel_read", 5)
                self.dbg.debug_dma(self.px_write_dma, "pixel write", "pixel_write", 6)

                self.dbg.debug_pio_status(sm0=True, sm1=True)

            if self.debug_with_debug_bytes:
                self.dbg.print_debug_bytes(self.debug_bytes1)

        print("{{ END OF IMAGE DRAW LOOP }}")
        # self.reset()

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

        prof.start_profile('scaler.fill_address_list')
        # Fill it using viper function
        # self.fill_address_list(
        #     self.get_all_interp_addrs(scaled_height))


        prof.end_profile('scaler.fill_address_list')

        if False and self.debug_interp_list:
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

        return True

    def feed_interp_addr(self, scaled_height):
        print(f"** Feeding addresses up to {scaled_height}")

        if self.debug_interp_list:
            print(f"SM PUT: ")

        # for i in range(0, scaled_height):
        for i in range(0, 1):
            new_write = mem32[INTERP0_PEEK_LANE0]
            new_read = mem32[INTERP0_POP_LANE1]

            if self.debug_interp_list:
                print(f"\t W:0x{new_write:08X}")
                print(f"\t R:0x{new_read:08X}")

            self.sm_read_addr.put(new_write) # write addr
            self.sm_read_addr.put(new_read)    # read addr

        self.dbg.print_debug_bytes(self.debug_bytes1)

        print()
        # self.sm_read_addr.put(0x00000000)  # NULL terminator


    def init_interp_sprite(self, read_base, write_base, sprite_width):
        row_width_4bit = math.ceil(sprite_width / 2)

        if self.debug_interp:
            print(f"* INTERP SPRITE:")
            print(f"\t row_width: {row_width_4bit}")
            print(f"\t write_base: 0x{write_base:08X}")
            print(f"\t read_base: 0x{read_base:08X}")

        # Remaining interp config

        # Common control config for address generation
        ctrl_config = (
                (0 << 0) |  # No shift
                (0 << 5) |  # Mask LSB = 0
                (31 << 10) |  # Full 32-bit mask
                (0 << 15)   # FORCE_MSB = 0
        )

        # INTERP0 for write addresses (display)
        mem32[INTERP0_BASE0] = self.display_stride  # write step
        mem32[INTERP0_BASE1] = row_width_4bit     # read step
        mem32[INTERP0_BASE2] = 0

        # 1. We use ACCUM0 for the WRITE initial address offset and ACCUM1 for the READ
        # 2. Substract one interval from the base addr, to avoid skipping 1st row
        mem32[INTERP0_ACCUM0] = write_base
        mem32[INTERP0_ACCUM1] = read_base - (row_width_4bit*2)

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


    @micropython.viper
    def fill_address_list(self, arr_ptr: ptr32, write_base_reg: ptr32, read_base_reg: ptr32, size: int):
        idx = 0
        while idx < size:
            write_addr = ptr32(write_base_reg)[0]  # Reads from POP registers
            read_addr = ptr32(read_base_reg)[0]

            arr_ptr[idx * 2] = write_addr
            arr_ptr[idx * 2 + 1] = read_addr
            idx += 1

        """ Add null terminator, to trigger the null IRQ on CH. 2 (row_addr)"""
        arr_ptr[size * 2] = 0

    def init_dma(self):
        """Set up the complete DMA chain for sprite scaling"""

        """ CH:2 Row address control DMA """
        row_addr_ctrl = self.row_addr.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=False,  # Reads from FIFO
            inc_write=False,  # Fixed write target
            treq_sel=DREQ_PIO1_RX1,
            irq_quiet=False
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
            # write=0, # For debug bytes
            ctrl=row_addr_target_ctrl,
        )

        """ CH:4 Color lookup DMA """
        color_lookup_ctrl = self.color_lookup.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses
            inc_read=False,
            inc_write=False,  # always writes to DMA WRITE
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.row_addr_target.channel,
            irq_quiet=False
        )

        self.color_lookup.config(
            count=0, # TBD
            read=PIO1_RX0,  # read/write TARGET address block array
            write=WRITE_DMA_BASE + DMA_READ_ADDR_TRIG,
            ctrl=color_lookup_ctrl
        )
        self.color_lookup.irq(handler=self.irq_px_read)


        """ CH:5. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read_dma.pack_ctrl(
            size=2,
            inc_read=True,      # Through sprite data
            inc_write=False,    # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO1_TX0,
            bswap=True,
            irq_quiet=False
        )

        # tx_per_row = (width + 1) // 2  # Round up for 4-bit pixels
        # print(f"tx_per_row: {tx_per_row}")

        self.px_read_dma.config(
            count=0,
            read=0,  # To be Set per row
            write=PIO1_TX0,
            ctrl=px_read_ctrl
        )

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
            self.dbg.debug_pio_status(sm0=True, sm1=True)

    def init_dma_sprite(self, scaled_height, scaled_width):
        """ Sprite-specific DMA configuration goes here """
        px_per_tx = PX_READ_BYTE_SIZE * 2
        tx_per_row = (scaled_width+1) // px_per_tx

        self.px_read_dma.config(count=tx_per_row)
        self.color_lookup.config(count=scaled_width)

        print("DMA CONFIG'D for: ")
        print(f"\t s.height / s.width = {scaled_height} / {scaled_width}")
        print(f"\t px_per_tx = {px_per_tx}")
        print(f"\t tx_per_row = {tx_per_row}")
        print(f"\t count - px_read_dma: {tx_per_row}")
        print(f"\t count - color_lookup: {scaled_width}")

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
        self.sm_read_addr.active(0)
        self.px_write_dma.active(0)
        self.color_lookup.active(0)

        self.rows_read_count = 0

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
        self.sm_read_addr.restart()
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)


    def irq_px_read(self, channel):
        if self.debug:
            print("*** PX READ FINISH IRQ ***")
            print(f"# rows_read_count: {self.rows_read_count}")
            print()
        # self.feed_address_pair()
        self.rows_read_count += 1




