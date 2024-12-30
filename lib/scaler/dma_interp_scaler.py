import asyncio
import time

import math

import sys
from _rp2 import DMA, StateMachine
from uarray import array
from uctypes import addressof

from images.indexed_image import Image
from scaler.dma_scaler_const import *
from scaler.dma_scaler_pio import read_palette, read_addr, pixel_skip
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
        self.addr_idx = 0
        self.display = display
        self.h_patterns = {} # Horizontal scaling patterns

        """ Create array with maximum possible number of addresses """
        self.value_addrs = array('L', [0] * ((display.height * 2)+2))
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
        self.debug_pio = False
        self.debug_irq = False
        self.debug_interp = False
        self.debug_interp_list = False
        self.debug_with_debug_bytes = False

        self.draw_x = 0
        self.draw_y = 0

        if self.debug_with_debug_bytes:
            print(" * DEBUG BYTES ADDR *")
            print(f" * 0x{addressof(self.debug_bytes1):08X}")
            print(f" * 0x{addressof(self.debug_bytes2):08X}")

        self.display_stride = self.display.width * 2
        display_pixels = (self.display.height) * self.display_stride
        self.max_write_addr = self.display.trans_addr + display_pixels

        self.fill_target_addrs()

        """ Transparency:
         2 sets of addresses for read / write. 1 block equals all 4 pairs
         """
        # self.px_skip_read_addrs = array('L', [0]*4)
        # self.px_skip_read_addrs[0] = 0x00000000     # disable px_write w. addr
        # self.px_skip_read_addrs[1] = DMA_PX_WRITE_BASE + DMA_TRANS_COUNT_TRIG
        # self.px_skip_read_addrs[2] = SNIFF_DATA
        # self.px_skip_read_addrs[3] = PIO1_RX2

        """ SKIP_CTRL values"""
        self.px_skip_values = array('L', [0] * 2)
        self.px_skip_values[0] = 0x00000000
        self.px_skip_values[1] = DMA_PX_WRITE_BASE + DMA_TRANS_COUNT_TRIG

        skip_values = int(addressof(self.px_skip_values))
        print(f" - SKIP VALUES ADDR: 0x{skip_values:08x}")

        """ Define 4, 3-word, control blocks for SKIP_CTRL. 
        Using AL1 all 4 words:
        0x10 (Alias 1) CTRL READ_ADDR WRITE_ADDR TRANS_COUNT_TRIG
        """
        buff = aligned_buffer(4*16)
        # self.px_skip_ctrl = array('L', [0] * 16)
        self.px_skip_ctrl = array('L', buff)
        print(f" - PX SKIP CTRL BLOCKS ADDR: 0x{addressof(self.px_skip_ctrl):08x}")

        ctrl_treq = 0x274839
        ctrl_no_treq = 0x3FC839

        self.px_skip_ctrl[0] = ctrl_treq
        self.px_skip_ctrl[1] = skip_values
        self.px_skip_ctrl[2] = DMA_PX_WRITE_BASE + DMA_WRITE_ADDR
        self.px_skip_ctrl[3] = 0x00000001

        self.px_skip_ctrl[4] = ctrl_no_treq
        self.px_skip_ctrl[5] = skip_values
        self.px_skip_ctrl[6] = DMA_HORIZ_SCALE_BASE + DMA_WRITE_ADDR_TRIG
        self.px_skip_ctrl[7] = 0x00000001

        self.px_skip_ctrl[8] = ctrl_no_treq
        self.px_skip_ctrl[9] = SNIFF_DATA
        self.px_skip_ctrl[10] = PIO1_TX2
        self.px_skip_ctrl[11] = 0x00000001

        self.px_skip_ctrl[12] = ctrl_treq
        self.px_skip_ctrl[13] = PIO1_RX2
        self.px_skip_ctrl[14] = DMA_PX_WRITE_BASE + DMA_WRITE_ADDR
        self.px_skip_ctrl[15] = 0x00000001

        # self.px_skip_ctrl[16] = 0x00000000 # NULL terminator
        # self.px_skip_ctrl[17] = 0x00000000 # NULL terminator
        # self.px_skip_ctrl[18] = 0x00000000 # NULL terminator
        # self.px_skip_ctrl[19] = 0x00000000 # NULL terminator

        # DEBUG
        # debug_bytes = addressof(self.debug_bytes1)
        # self.px_skip_ctrl[1] = debug_bytes
        # self.px_skip_ctrl[3] = debug_bytes
        # self.px_skip_ctrl[5] = debug_bytes
        # self.px_skip_ctrl[7] = debug_bytes

        # DEBUG
        # self.px_skip_addrs[0] = addressof(self.debug_bytes1)

        # DMA Channels
        self.row_addr = DMA()               # 2. Vertical / row control (read and write)
        self.row_addr_target = DMA()        # 3. Uses ring buffer to tell row_addr where to write its address to
        self.color_lookup = DMA()           # 4. Palette color lookup / transfer
        self.px_read_dma = DMA()            # 5. Sprite data
        self.px_write_dma = DMA()           # 6. Display output
        self.h_scale = DMA()                # 7. Horizontal scale pattern
        # self.addr_skip = DMA()              # 8. Pixel skip / transparency
        # self.skip_ctrl = DMA()              # 9. Pixel skip control

        self.palette_addr = None

        sm_freq = 40_000_000
        # PIO1 - SM0
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=sm_freq,
            sideset_base=8
        )
        # PIO1 - SM1
        self.sm_read_addr = StateMachine(
            5, read_addr,
            freq=sm_freq,
        )
        # PIO1 - SM2
        # self.sm_pixel_skip = StateMachine(
        #     6, pixel_skip,
        #     freq=sm_freq,
        #     sideset_base=9
        # )

        self.init_patterns()
        self.init_dma()

    def fill_target_addrs(self):
        """" Add 2 target blocks:
                    1. pixel reader READ addr
                    2. pixel writer WRITE addr
                """
        self.target_addrs = array('L', [0] * 2)

        # Write addr, then read addr + trigger
        self.target_addrs[0] = int(DMA_BASE_6 + DMA_WRITE_ADDR)
        # self.target_addrs[1] = int(SNIFF_DATA)  # Sniffer seed value will be sent here
        # self.target_addrs[2] = int(SNIFF_DATA)  # Sniffer seed value (repeat)
        self.target_addrs[1] = int(DMA_BASE_5 + DMA_READ_ADDR_TRIG)

        print("~~ TARGET ADDRESSES: ~~")
        for addr in self.target_addrs:
            print(f"\t- 0x{addr:08x}")

    def fill_value_addrs(self, scaled_height):
        """ Uses INTERP to fill a sequence of Read/Write addresses indicating the start of each sprite row, and the
        start of the display row to draw it in """

        prof.start_profile('scaler.prefill_addrs')
        max_height = scaled_height * 2
        for i in range(0, max_height, 2):
            write_addr = mem32[INTERP0_POP_FULL]
            self.value_addrs[i] = write_addr            # write addr
            if self.value_addrs[i] > self.max_write_addr:
                break

            # self.value_addrs[i + 1] = write_addr + 2    # sniffer addr. We preadd the +2 to make it easier to skip later on
            # self.value_addrs[i + 2] = write_addr + 2    # sniffer addr. repeat
            self.value_addrs[i + 1] = mem32[INTERP1_POP_FULL]   # read addr

        prof.end_profile('scaler.prefill_addrs')

        if self.debug_interp_list:
            print("~~ Value Addresses ~~")
            for i in range(0, scaled_height * 2, 2):
                write = self.value_addrs[i]
                # sniff = self.value_addrs[i+1]
                # sniff2 = self.value_addrs[i+2]
                read = self.value_addrs[i+1]
                print(f"W [{i//4:02}]: 0x{write:08X}")
                # print(f"S     : ....0x{sniff:08X}")
                # print(f"S     : ....0x{sniff2:08X}")
                print(f"R     : ....0x{read:08X}")

    def draw_sprite(self, meta:SpriteType, x, y, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """
        self.draw_x = x
        self.draw_y = y
        prof.start_profile('scaler.reset')
        self.reset()
        prof.end_profile('scaler.reset')

        prof.start_profile('scaler.scaled_width_height')
        scaled_height = meta.height * v_scale
        self.scaled_height = scaled_height
        scaled_width = meta.width * v_scale
        self.scaled_width = scaled_width
        prof.end_profile('scaler.scaled_width_height')

        # Set up base addresses

        """ INTERPOLATOR CONFIGURATION --------- """
        # base_write = int(self.display.write_addr + (((y * self.display.width) + x)*2))
        base_write = int(addressof(self.display.buffer2))

        if self.debug_dma:
            print(f"Drawing a sprite of {meta.width}x{meta.height} @ base addr 0x{base_write:08X}")
        if not self.last_sprite_class or (self.last_sprite_class.name != meta.name):
            """ The following values can be cached from one sprite draw to the next, provided they are the same 
            Sprite type """
            prof.start_profile('scaler.cache_sprite_config')

            self.base_read = addressof(image.pixel_bytes)

            if meta.width == 32:
                self.frac_bits = 4  # Use x.y fixed point (32x32)
            elif meta.width == 16:
                self.frac_bits = 3  # Use x.y fixed point   (16x16)
            else:
                print("ERROR: only 16x16 or 32x32 sprites allowed")
                sys.exit(1)

            # INTERP0: Write address generation (display)
            write_ctrl_config = (
                    (0 << 0) |  # No shift needed for write addresses
                    (0 << 5) |  # No mask needed
                    (31 << 10) |  # Full 32-bit mask
                    (0 << 15)  # No sign
            )
            mem32[INTERP0_CTRL_LANE0] = write_ctrl_config
            mem32[INTERP0_CTRL_LANE1] = write_ctrl_config

            prof.end_profile('scaler.cache_sprite_config')

        self.last_sprite_class = meta

        """ Config interpolator """
        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(self.base_read, base_write, scaled_width, scaled_height, v_scale)
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
            print(f"    SPRITE READ BASE ADDR:     0x{self.base_read:08X}")
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
        # self.dbg.debug_dma(self.addr_skip, "addr skip", "addr_skip", 8)
        # self.dbg.debug_dma(self.skip_ctrl, "skip control", "skip_ctrl", 9)

        if self.debug_pio:
            self.dbg.debug_pio_status(sm0=True, sm1=True)

    def start(self, scaled_height):
        # This is only to avoid a mem error within the IRQ handler
        prof.start_profile('scaler.irq_color_lookup')
        prof.end_profile('scaler.irq_color_lookup')

        self.addr_counter = 0

        prof.start_profile('scaler.start_channels')
        # self.sm_pixel_skip.active(1)
        self.sm_read_palette.active(1)
        self.sm_read_addr.active(1)

        """ Color lookup must be activated too, since it is right after a SM, so there's no direct way to trigger it"""
        self.color_lookup.active(1)
        self.h_scale.active(1)
        # self.addr_skip.active(1)
        self.row_addr_target.active(1)
        prof.end_profile('scaler.start_channels')

        prof.start_profile('scaler.start_feed_addresses')
        self.load_and_push_addr_set()  # preloads some addresses
        prof.end_profile('scaler.start_feed_addresses')

        while not self.read_finished:
            if self.debug_with_debug_bytes:
                self.dbg.print_debug_bytes(self.debug_bytes1)

            if self.debug_dma:
                print(f"\n~~ DMA CHANNELS in MAIN LOOP (Start()) (finished:{self.read_finished}) ~~~~~~~~~~~\n")
                self.debug_dma_and_pio()
                print()

    def finish_sprite(self):
        self.read_finished = True
        self.rows_read_count = 0
        self.addr_idx = 0
        self.copy_with_trans(self.draw_x, self.draw_y)

    def copy_with_trans(self, x, y):
        """ Copy the sprite from the "scratch" framebuffer to the final one in the display """
        disp = self.display
        disp.write_framebuf.blit(disp.trans_framebuf, x, y, 0)

    def init_interp_sprite(self, read_base, write_base, sprite_width, sprite_height, scale_y_one = 1.0):
        FRAC_BITS = self.frac_bits
        INT_BITS = 32 - FRAC_BITS

        """ Only Satan understands this formula, but it works """
        scale_y = sprite_width // (2 * scale_y_one ** 2)

        """
        scale_y = 1 # 500%
        scale_y = 2 # 400%
        scale_y = 4 # 400%
        scale_y = 8 # 200%
        scale_y = 16 # 100% <
        scale_y = 32 # 50%
        scale_y = 64 # 25%
        """

        # Calculate scaling values
        read_step = int((scale_y) * (1 << FRAC_BITS))  # Convert step to fixed point

        if self.debug_interp:
            int_bits_str = '^' * INT_BITS
            frac_bits_str = '`' * FRAC_BITS
            print(f"* INTERP SPRITE:")
            print(f"\t write_base:      0x{write_base:08X}")
            print(f"\t read_base:       0x{read_base:08X}")
            print(f"\t step:            0x{read_step:08X}")
            print(f"\t step b.:         {read_step:>032b}")
            print(f"\t int/frac bits:   {int_bits_str}{frac_bits_str}")

        # For write addresses we want: BASE0 + ACCUM0
        mem32[INTERP0_BASE0] = 0  # Base address component
        mem32[INTERP0_BASE1] = self.display_stride  # Row increment. Increasing beyond stride can be used to skew sprites.
        mem32[INTERP0_ACCUM0] = write_base  # Starting address

        # INTERP1: Read address generation with scaling
        read_ctrl_lane0 = (
                (0 << 0) |  # No shift on accumulator/raw value
                # ((FRAC_BITS) << 10) | # mask full (MSB)
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

        self.fill_value_addrs(self.scaled_height)

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

    def init_sniff(self):
        pass

    def init_dma(self):
        """Set up the complete DMA chain for sprite scaling"""

        """ CH:2 Row address control DMA """
        row_addr_ctrl = self.row_addr.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=False,  # Reads from FIFO
            inc_write=False,  # Fixed write target

        )

        self.row_addr.config(
            count=1,
            read=PIO1_RX1,
            ctrl=row_addr_ctrl
        )

        """ CH:3 Row address target DMA """
        row_addr_target_ctrl = self.row_addr_target.pack_ctrl(
            size=2,             # 32-bit control blocks
            inc_read=True,      # Step through ringed control blocks / addrs
            inc_write=False,    # always write to DMA2 WRITE
            ring_sel=0,         # ring on read channel (read/write TARGET address)
            # ring_size=4,  # 2^x or x bytes for 3 addresses in ring buffer to loop through (read, sniffer & write)
            ring_size=3,        # 2^x or x bytes for 2 addresses in ring buffer to loop through (read&write)
            chain_to=self.h_scale.channel,
            treq_sel=DREQ_PIO1_RX1, # Crucial for sync'ing with SM
        )

        self.row_addr_target.config(
            count=2, # We are sending 2 addresses
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
            treq_sel=DREQ_PIO1_RX0,
            # chain_to=self.addr_skip.channel
        )

        self.color_lookup.config(
            count=1, # TBD
            read=PIO1_RX0,
            write=WRITE_DMA_BASE + DMA_READ_ADDR,
            ctrl=color_lookup_ctrl,
        )

        """ CH:6. Display write DMA --------------------------- """
        px_write_ctrl = self.px_write_dma.pack_ctrl(
            size=1, # 16 bit pixels
            inc_read=False,  # from PIO
            inc_write=True,  # Through display
            chain_to=self.color_lookup.channel,
            high_pri=True
        )

        self.px_write_dma.config(
            count=1,
            write=0, # TBD
            ctrl=px_write_ctrl
        )

        """ CH:7. Horiz. scale DMA --------------------------- """
        h_scale_ctrl = self.h_scale.pack_ctrl(
            size=2,
            treq_sel=DREQ_PIO1_RX0,
            inc_read=True,
            inc_write=False,
            ring_sel=False,  # ring on read
            ring_size=4,    # n bytes = 2^n
            # high_pri=True,
            irq_quiet=False,
            chain_to=self.row_addr_target.channel
        )

        self.h_scale.config(
            count=1,
            # read=xxx,  # Current horizontal pattern (to be set later)
            write=WRITE_DMA_BASE + DMA_TRANS_COUNT_TRIG,
            ctrl=h_scale_ctrl
        )
        self.h_scale.irq(handler=self.irq_row_end)

        """ CH:8. Address skip DMA (transparent px) ------------------- 
        This channel performs a series of actions by using a write ring buffer:
            1. Disable write addr on px_write DMA
            2. Trigger horiz_scale DMA
            3. Reload write addr from sniffer 
            4. Push write addr to pixel_skip SM
            5  pixel_skip SM doubles addr 
            6. Read SM2 RX for final addr
            7. Write to px_write w. addr to restore for next pixel
        The read addresses are provided by the pixel_skip SM, hardcoded in the code.
        """
        # addr_skip_ctrl = self.addr_skip.pack_ctrl(
        #     size=2,
        #     inc_read=True,
        #     inc_write=True,
        #     chain_to=self.skip_ctrl.channel,
        #     treq_sel=DREQ_PIO1_RX2,
        #
        # )
        # print(f":::CTRL CODE::: 0x{addr_skip_ctrl:04X}")
        #
        # self.addr_skip.config(
        #     count=1,
        #     ctrl=addr_skip_ctrl,
        #     read=PIO1_RX2,
        #     write=0,
        # )

        """ CH:9. Address Skip read / write  Configuration 
         The addr skip process requires some transfers from / to different addresses, which this DMA controls
         
         Well be using DMA Alias1:
         0x10 (Alias 1) CTRL READ_ADDR WRITE_ADDR TRANS_COUNT_TRIG
         """
        # skip_ctrl_cfg = self.skip_ctrl.pack_ctrl(
        #     size=2,
        #     inc_read=True,
        #     inc_write=True,
        #     ring_sel=False,  # Ring on read
        #     ring_size=6, # Verified for 4 words (ctrl, read, write, tx)
        # )
        #
        # self.skip_ctrl.config(
        #     count=16, # Because we are writing to the Aliased trigger registers, which contain 4 words
        #     ctrl=skip_ctrl_cfg,
        #     read=addressof(self.px_skip_ctrl),
        #     # write=DMA_ADDR_SKIP + DMA_CTRL_AL3,
        #     write=addressof(self.debug_bytes1),
        # )

        if self.debug_dma:
            print("~~ DMA CHANNELS in INIT_DMA ~~~~~~~~~~~")
            self.debug_dma_and_pio()

    def init_dma_sprite(self, height, width, h_scale=1.0):
        """ Sprite-specific DMA configuration goes here """

        prof.start_profile('scaler.dma_sprite_config')
        self.color_lookup.count = width
        # self.color_lookup.count = 1

        tx_per_row = math.ceil(width / self.px_per_tx)
        self.px_read_dma.count = tx_per_row
        prof.end_profile('scaler.dma_sprite_config')

        prof.start_profile('scaler.h_pattern')
        h_pattern_arr = self.h_patterns[h_scale]
        self.h_scale.read = h_pattern_arr
        self.h_scale.count = width
        prof.end_profile('scaler.h_pattern')

        if self.debug_dma:
            print("DMA CONFIG'D for: ")
            print(f"\t h_scale = {h_scale}")
            print(f"\t height / width = {height} / {width}")
            print(f"\t px_per_tx = {self.px_per_tx}")
            print(f"\t tx_per_row = {tx_per_row}")
            print(f"\t count - color_lookup: {width}")
            print(f"\t h_scale addr:        0x{addressof(h_pattern_arr):08X}")

            print()
            print("~~ DMA AFTER SPRITE CONFIG ~~~~~~~")
            self.debug_dma_and_pio()

    def irq_row_end(self, ch=None):
        if self.debug_irq:
            print(">> START LOOP AT IRQ_ROW_END")

        """
         check flag for NOT "TXFULL"
        """

        if self.is_fifo_full():
            if self.debug_irq:
                print(">>> FIFO IS FULL - Returning")

            """ Fifo is full """
            return True
        else:
            if self.sm_read_addr.tx_fifo() < 2:
                self.load_and_push_addr_set()

    def is_fifo_full(self):
        return self.sm_read_addr.tx_fifo() == 4

        fifo_status = mem32[PIO1_BASE + PIO_FSTAT]
        fifo_status = fifo_status >> 16 + 1  # Bit #1 is the flag for TX_FULL > SM 1
        fifo_full = fifo_status & 0x0000000F
        fifo_full_sm1 = fifo_full & 0b0000000000000000000000000001
        return fifo_full_sm1

    def load_addr_pair(self, idx):
        prof.start_profile('scaler.interp_pop')
        new_write = self.value_addrs[idx]
        # new_sniffer = self.value_addrs[idx + 1]
        # new_sniffer = self.value_addrs[idx + 2]
        new_read = self.value_addrs[idx + 1]
        prof.end_profile('scaler.interp_pop')

        if self.debug_interp_list:
            print(f"READ ADDR PAIR: (#{idx//4})")
            print(f"\t W:0x{new_write:08X}")
            # print(f"\t S:0x{new_sniffer:08X}")
            print(f"\t R:0x{new_read:08X}")

        return new_write, new_read

    def push_addr_set(self, new_write, new_read):
        prof.start_profile('scaler.interp_sm_put')

        self.sm_put(new_write)
        # self.sm_put(new_sniffer)
        # self.sm_put(new_sniffer)
        self.sm_put(new_read)

        self.addr_idx += 2
        self.rows_read_count = self.addr_idx

        if self.debug_pio:
            print(f"2 addrs put in SM1 (addr_idx:{self.addr_idx})")

        prof.end_profile('scaler.interp_sm_put')

    def sm_put(self, addr):
        """ Put an address into the 'read addr' SM, but only if the TX FIFO is not full """
        self.sm_read_addr.put(addr)
        if self.debug:
            print(f" * Addr 0x{addr:08X} PUT into SM")

    def load_and_push_addr_set(self):
        idx = self.addr_idx
        new_write, new_read = self.load_addr_pair(idx)
        # new_sniffer = new_write+2

        if (new_write == 0) and (new_read == 0):
            if self.debug:
                print("~000 ZERO ADDR = NULL TRIGGER 000~")
            self.finish_sprite()
            return False

        """ check bounds """
        prof.start_profile('scaler.check_bounds')
        if new_write > self.max_write_addr:
            print("** BOUNDS EXCEEDED **")
            self.finish_sprite()
            return False
        prof.end_profile('scaler.check_bounds')

        self.push_addr_set(new_write, new_read)

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
            if self.debug:
                print(f"SCALE PATTERNS: {key} for {val}")
            array_pattern = self.create_aligned_pattern(val)
            self.h_patterns[key] = array_pattern

        # Calculate pattern sums for DMA transfer counts
        # self.h_pattern_sums = {
        #     scale: sum(pattern) for scale, pattern in self.h_patterns.items()
        # }

    def create_aligned_pattern(self, list):
        # Create ALIGNED array for scaling patterns
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
        # self.sm_pixel_skip.active(0)
        self.px_write_dma.active(0)
        self.color_lookup.active(0)
        # self.addr_skip.active(0)
        # self.skip_ctrl.active(0)

        self.rows_read_count = 0
        self.addr_idx = 0
        self.read_finished = False

        # Clear interpolator accumulators
        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0

        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

    def init_pio(self, palette_addr):
        # self.sm_pixel_skip.restart()
        self.sm_read_addr.restart()
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)

    async def async_start_feed(self):
        print("~~@ IN async_start_feed() @~~")
        asyncio.run(self.async_feed_addresses())

    async def async_feed_addresses(self):
        """ This loop runs constantly waiting for a chance to feed the SM with a new set of write and read addresses."""
        while True:

            """
             PIO1_BASE + PIO_FSTAT
             SM:   1   2   3   4
                   16, 17, 18, 19
             check for NOT TXFULL
            """
            """ USE StateMachine.tx_fifo()!!! """
            fifo_status = mem32[PIO1_BASE + PIO_FSTAT]
            fifo_status = fifo_status >> 16 + 1 # Bit #1 is the flag for TX_FULL > SM 1
            fifo_status = fifo_status & 0x0000000F
            fifo_status_sm1 = fifo_status & 0b0000000000000000000000000001

            if fifo_status_sm1:
                """ Fifo is full, do another lap"""
                if self.debug:
                    print(f"!! FIFO TX FULL !! - b{fifo_status:>04b}")
                continue
            else:
                if self.debug:
                    print(f"__ FIFO TX NOT FULL __ - b{fifo_status:>04b}")

                idx = self.addr_idx

                prof.start_profile('scaler.interp_pop')
                new_write = self.value_addrs[idx]
                # new_sniff = self.value_addrs[idx+1]
                # new_sniff2 = self.value_addrs[idx+2]
                new_read = self.value_addrs[idx+1]
                prof.end_profile('scaler.interp_pop')

                """ check bounds """
                prof.start_profile('scaler.check_bounds')
                if new_write > self.max_write_addr:
                    print("** BOUNDS EXCEEDED **")
                    self.finish_sprite()
                    return False
                prof.end_profile('scaler.check_bounds')

                if self.debug_interp_list:
                    print(f"READ ADDR PAIR: (#{idx})")
                    print(f"\t W:0x{new_write:08X}")
                    print(f"\t R:0x{new_read:08X}")

                if (new_write == 0) and (new_read == 0):
                    if self.debug:
                        print("~000 ZERO ADDR RETURNING FALSE 000~")
                    self.finish_sprite()
                    return False

                prof.start_profile('scaler.interp_sm_put')
                self.sm_read_addr.put(new_write)
                # self.sm_read_addr.put(new_sniff)
                # self.sm_read_addr.put(new_sniff2)
                self.sm_read_addr.put(new_read)
                prof.end_profile('scaler.interp_sm_put')

                self.addr_idx += 2
                self.rows_read_count = self.addr_idx

