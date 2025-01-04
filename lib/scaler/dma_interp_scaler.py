import asyncio
import time

import math

import sys

from _rp2 import DMA, StateMachine
from uarray import array
from uctypes import addressof

from images.indexed_image import Image
from scaler.dma_scaler_const import *
from scaler.dma_scaler_pio import read_palette, read_addr
from scaler.dma_scaler_debug import ScalerDebugger
from profiler import Profiler as prof, timed
from sprites2.sprite_types import SpriteType
from ssd1331_pio import SSD1331PIO
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
        self.display:SSD1331PIO = display
        self.h_patterns = {} # Horizontal scaling patterns

        """ Create array with maximum possible number of addresses """
        read_buf = aligned_buffer((32+1)*4) # Max sprite supported is 32x32, but we add +1 for the null trigger
        write_buf = aligned_buffer((display.height+1)*4)
        self.read_addrs = array('L', read_buf)
        self.write_addrs = array('L', write_buf)

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
        self.debug = True
        self.debug_dma = False
        self.debug_pio = True
        self.debug_irq = True
        self.debug_interp = True
        self.debug_interp_list = False
        self.debug_with_debug_bytes = False

        self.draw_x = 0
        self.draw_y = 0
        self.alpha = None

        self.disp_width = 0
        self.disp_height = 0

        if self.debug_with_debug_bytes:
            print(" * DEBUG BYTES ADDR *")
            print(f" * 0x{addressof(self.debug_bytes1):08X}")
            print(f" * 0x{addressof(self.debug_bytes2):08X}")

        disp_width = self.display.width
        disp_height = self.display.height

        """ Calculate write address and strides """
        self.trans_framebuf = self.display.trans_framebuf_32

        # DMA Channels
        self.read_addr = DMA()               # 2. Vertical / row control (read and write)
        self.write_addr = DMA()        # 3. Uses ring buffer to tell read_addr where to write its address to
        self.color_lookup = DMA()           # 4. Palette color lookup / transfer
        self.px_read = DMA()            # 5. Sprite data
        self.px_write = DMA()           # 6. Display output
        self.h_scale = DMA()                # 7. Horizontal scale pattern
        # self.addr_push = DMA()              # 8. Read/write address pushing channel

        self.ch_names = {
            0: None,
            1: None,
            2: "read_addr",
            3: "write_addr",
            4: "color_lookup",
            5: "px_read",
            6: "px_write",
            7: "h_scale",
        }

        self.palette_addr = None

        sm_freq = 10_000_000 # must be 75% of the system freq or less, to avoid visual glitches
        # PIO1 - SM0
        self.sm_read_palette = StateMachine(
            4, read_palette,
            freq=sm_freq,
            sideset_base=8
        )

        self.init_patterns()
        self.init_dma()

    def fill_target_addrs(self):
        # DEPRECATED
        """" Add 2 target blocks:
                    1. pixel reader READ addr
                    2. pixel writer WRITE addr
                """
        self.target_addrs = array('L', [0] * 2)

        # Write addr, then read addr + trigger
        self.target_addrs[0] = int(DMA_BASE_6 + DMA_WRITE_ADDR)
        self.target_addrs[1] = int(DMA_BASE_5 + DMA_READ_ADDR_TRIG)

        print("~~ TARGET ADDRESSES: ~~")
        for addr in self.target_addrs:
            print(f"\t- 0x{addr:08x}")

    def fill_addrs(self, scaled_height):
        """ Uses INTERP to fill a sequence of Read/Write addresses indicating the start of each sprite row, and the
        start of the display row to draw it in """

        prof.start_profile('scaler.prefill_addrs')
        scaled_height = int(scaled_height)
        for i in range(0, scaled_height):
            write_addr = mem32[INTERP0_POP_FULL]
            if write_addr > self.max_write_addr:
                break

            self.write_addrs[i] = write_addr            # write addr
            self.read_addrs[i] = mem32[INTERP1_POP_FULL]   # read addr

        self.read_addrs[scaled_height+1] = 0x00000000 # NULL trigger
        prof.end_profile('scaler.prefill_addrs')

        if self.debug_interp_list:
            print("~~ Value Addresses ~~")
            for i in range(0, scaled_height + 1):
                write = self.write_addrs[i]
                read = self.read_addrs[i]
                print(f"W [{i:02}]: 0x{write:08X}")
                print(f"R     : ....0x{read:08X}")

    def draw_sprite(self, meta:SpriteType, x, y, image:Image, h_scale=1.0, v_scale=1.0):
        """
        Draw a scaled sprite at the specified position.
        This method is synchronous (will not return until the whole sprite has been drawn)
        """
        self.init_interp()
        self.read_finished = False

        prof.start_profile('scaler.reset')
        self.draw_x = x
        self.draw_y = y
        self.alpha = meta.alpha_color
        prof.end_profile('scaler.reset')

        prof.start_profile('scaler.scaled_width_height')
        scaled_height = meta.height * v_scale
        scaled_width = meta.width * v_scale

        self.scaled_height = scaled_height
        self.scaled_width = scaled_width
        prof.end_profile('scaler.scaled_width_height')

        """ The following values can be cached from one sprite draw to the next, provided they are the same 
        Sprite type (TBD)  """
        prof.start_profile('scaler.cache_sprite_config')

        self.base_read = addressof(image.pixel_bytes)

        if meta.width == 32:
            self.frac_bits = 4  # Use x.y fixed point (32x32)
        elif meta.width == 16:
            self.frac_bits = 3  # Use x.y fixed point   (16x16)
        else:
            print("ERROR: only 16x16 or 32x32 sprites allowed")
            sys.exit(1)

        prof.end_profile('scaler.cache_sprite_config')

        self.last_sprite_class = meta
        self.base_read = addressof(image.pixel_bytes)
        # Set up base addresses

        prof.start_profile('scaler.setup_buffers')

        """
        We implement transparency by first drawing the sprite on a scratch framebuffer.
        There are several sizes to optimize this process.
        
        Here we the right framebuffer based on the (scaled) sprite dimensions
        """
        if scaled_width <= 8:
            self.trans_framebuf = self.display.trans_framebuf_8
            self.disp_width = self.disp_height = 8
        elif scaled_width <= 16:
            self.trans_framebuf = self.display.trans_framebuf_16
            self.disp_width = self.disp_height = 16
        elif scaled_width <= 32:
            self.trans_framebuf = self.display.trans_framebuf_32
            self.disp_width = self.disp_height = 32
        else:
            self.trans_framebuf = self.display.trans_framebuf_full
            self.disp_width = self.display.width
            self.disp_height = self.display.height


        # DEBUG
        # self.trans_framebuf = self.display.trans_framebuf_full
        # disp_width = self.display.width
        # disp_height = self.display.height

        # Since all 3 framebufs use the same buffer, the memory address is also the same
        # base_write = self.display.read_addr
        # disp_width = self.display.width

        prof.end_profile('scaler.setup_buffers')

        # if self.debug_dma:
            # print(f"Drawing a sprite of {meta.width}x{meta.height} @ base addr 0x{base_write:08X}")
            # print(f"Display Stride: {self.display_stride}")

        """ Config interpolator """
        prof.start_profile('scaler.init_interp_sprite')
        self.init_interp_sprite(self.base_read, scaled_width, scaled_height, v_scale)
        prof.end_profile('scaler.init_interp_sprite')

        prof.start_profile('scaler.init_pio')
        palette_addr = addressof(image.palette_bytes)
        self.init_pio(palette_addr)
        self.palette_addr = palette_addr
        prof.end_profile('scaler.init_pio')

        prof.start_profile('scaler.init_dma_sprite')
        self.init_dma_sprite(meta.height, meta.width, scaled_height, h_scale)
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

    def debug_dma_and_pio(self):
        self.dbg.debug_dma(self.read_addr, "read address", "read_addr", 2)
        self.dbg.debug_dma(self.write_addr, "write address", "write_addr", 3)
        self.dbg.debug_dma(self.color_lookup, "color_lookup", "color_lookup", 4)
        self.dbg.debug_dma(self.px_read, "pixel read", "pixel_read", 5)
        self.dbg.debug_dma(self.px_write, "pixel write", "pixel_write", 6)
        self.dbg.debug_dma(self.h_scale, "horiz_scale", "horiz_scale", 7)

        if self.debug_pio:
            self.dbg.debug_pio_status(sm0=True)

    def start(self, scaled_height):
        # This is only to avoid a mem error within the IRQ handler
        prof.start_profile('scaler.irq_color_lookup')
        prof.end_profile('scaler.irq_color_lookup')

        prof.start_profile('scaler.start_channels')

        """ Color lookup must be activated too, since it is right after a SM, so there's no direct way to trigger it"""

        # self.color_lookup.active(1)
        self.h_scale.active(1)
        self.write_addr.active(1)
        self.sm_read_palette.active(1)

        prof.end_profile('scaler.start_channels')

        while not self.read_finished:
            if self.debug_with_debug_bytes:
                self.dbg.print_debug_bytes(self.debug_bytes1)

            if self.debug_dma:
                print(f"\n~~ DMA CHANNELS in MAIN LOOP (Start()) (finished:{self.read_finished}) ~~~~~~~~~~~\n")
                self.debug_dma_and_pio()
                print()

    def finish_sprite(self):
        prof.start_profile('scaler.finish_sprite')
        self.blit_with_trans(self.draw_x, self.draw_y)
        self.read_finished = True
        self.rows_read_count = 0
        self.addr_idx = 0
        self.reset()

        prof.end_profile('scaler.finish_sprite')

    def blit_with_trans(self, x, y):
        """ Copy the sprite from the "scratch" framebuffer to the final one in the display.
         This is needed to implement transparency """
        prof.start_profile('scaler.copy_with_trans')
        disp = self.display

        alpha = self.alpha
        print(f" ~ ALPHA IS {alpha} of Type {type(alpha)}")
        if alpha is None:
            disp.write_framebuf.blit(self.trans_framebuf, x, y)
        else:
            disp.write_framebuf.blit(self.trans_framebuf, x, y, int(alpha))

        prof.end_profile('scaler.copy_with_trans')

    def init_interp(self):
        """ One time interp configuration """
        prof.start_profile('scaler.interp_init')


        prof.end_profile('scaler.interp_init')

    def init_interp_sprite(self, read_base, sprite_width, sprite_height, scale_y_one = 1.0):
        prof.start_profile('scaler.interp_init_sprite')
        frac_bits = self.frac_bits
        int_bits = 32 - frac_bits
        base_write = self.display.trans_addr
        display_width = self.disp_width

        if self.debug_interp:
            print(f"* INTERP INIT:")
            print(f"\tread_base:    {read_base}")
            print(f"\twrite_base:   {base_write}")
            print(f"\tdisplay_width: {display_width}")
            print(f"\tsprite_height:{sprite_height}")
            print(f"\tscale_y_one:  {scale_y_one}")
            print(f"\t int/frac bits:   {int_bits}/{frac_bits}")

        """ INTERPOLATOR CONFIGURATION --------- """
        """ (read / write address generation) """
        write_ctrl_config = (
                (0 << 0) |  # No shift needed for write addresses
                (0 << 5) |  # No mask needed
                (31 << 10) |  # Full 32-bit mask
                (0 << 15)  # No sign
        )
        mem32[INTERP0_CTRL_LANE0] = write_ctrl_config
        mem32[INTERP0_CTRL_LANE1] = write_ctrl_config

        # INTERP1: Read address generation with scaling
        read_ctrl_lane0 = (
                (0 << 0) |  # No shift on accumulator/raw value
                (0 << 15) |  # No sign extension
                (1 << 16) |  # CROSS_INPUT - also add ACCUM1
                (1 << 18) |  # ADD_RAW - Enable raw accumulator addition
                (1 << 20)  # CROSS_RESULT - Use other lane's result
        )

        mem32[INTERP1_CTRL_LANE0] = read_ctrl_lane0

        """ Lane 1 config - handles integer extraction - must be reconfigured because it depends on self.frac_bits """
        read_ctrl_lane1 = (
                (self.frac_bits << 0) |  # Shift right to get integer portion
                (self.frac_bits << 5) |  # Start mask at bit 0
                ((32 - self.frac_bits) << 10) |  # Full 32-bit mask to preserve address
                (0 << 15) |  # No sign extension
                (1 << 18)  # ADD_RAW - Enable raw accumulator addition
        )
        mem32[INTERP1_CTRL_LANE1] = read_ctrl_lane1

        """ Only Satan understands this formula, but it works """
        scale_y = sprite_width // (2 * scale_y_one ** 2)
        # scale_y = sprite_width / 4 * scale_y_one

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
        read_step = int((scale_y) * (1 << frac_bits))  # Convert step to fixed point

        if self.debug_interp:
            int_bits_str = '^' * int_bits
            frac_bits_str = '`' * frac_bits
            print(f"* INTERP SPRITE:")
            print(f"\t write_base:      0x{base_write:08X}")
            print(f"\t read_base:       0x{read_base:08X}")
            print(f"\t read step (fixed):       0x{read_step:08X}")
            print(f"\t read step (fixed) b.:    {read_step:>032b}")
            print(f"\t int/frac bits:   {int_bits_str}{frac_bits_str}")
            print(f"\t scale_y:         {scale_y}")
            print(f"\t sprite_width:       {sprite_width}")

        prof.end_profile('scaler.interp_init_sprite')

        prof.start_profile('scaler.interp_config')

        self.display_stride = display_width * 2
        display_total_bytes = (self.disp_height) * self.display_stride
        self.max_write_addr = base_write + display_total_bytes

        # For write addresses we want: BASE0 + ACCUM0
        mem32[INTERP0_BASE0] = 0  # Base address component
        mem32[INTERP0_BASE1] = self.display_stride # Row increment. Increasing beyond stride can be used to skew sprites.
        mem32[INTERP0_ACCUM0] = base_write  # Starting address

        # Configure remaining variables
        mem32[INTERP1_BASE0] = 0  # # Row increment in fixed point
        mem32[INTERP1_BASE1] = read_step
        mem32[INTERP1_BASE2] = read_base # Base sprite read address
        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

        prof.end_profile('scaler.interp_config')

        self.fill_addrs(sprite_height)

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

        """ CH:2 Sprite read address DMA """
        read_addr_ctrl = self.read_addr.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=True,  # Reads from RAM
            inc_write=False,  # Fixed write target
            chain_to=self.color_lookup.channel,
        )

        self.read_addr.config(
            count=1,
            read=self.read_addrs,
            write=DMA_PX_READ_BASE + DMA_READ_ADDR_TRIG,
            ctrl=read_addr_ctrl
        )

        """ CH:3 Display write address DMA """
        write_addr_ctrl = self.write_addr.pack_ctrl(
            size=2,             # 32-bit control blocks
            inc_read=True,      # Step through write addrs
            inc_write=False,    # always write to DMA2 WRITE
            chain_to=self.read_addr.channel,
        )

        self.write_addr.config(
            count=1,
            read=addressof(self.write_addrs),          # read/write TARGET address block array
            write=DMA_PX_WRITE_BASE + DMA_WRITE_ADDR,
            ctrl=write_addr_ctrl,
        )

        """ CH:5. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read.pack_ctrl(
            size=2,
            inc_read=True,      # Through sprite data
            inc_write=False,    # debug_bytes: True / PIO: False
            treq_sel=DREQ_PIO1_TX0,
            bswap=True,
            irq_quiet=True
        )

        self.px_read.config(
            count=1,
            read=0,  # To be Set per row
            write=PIO1_TX0,
            ctrl=px_read_ctrl
        )
        self.px_read.irq(handler=self.irq_px_read_end)


        """ CH:4 Color lookup DMA """
        color_lookup_ctrl = self.color_lookup.pack_ctrl(
            size=2,  # 16bit colors in the palette, but 32 bit addresses
            inc_read=False,
            inc_write=False,  # always writes to DMA WRITE
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.write_addr.channel,
        )

        self.color_lookup.config(
            count=1, # TBD
            read=PIO1_RX0,
            write=WRITE_DMA_BASE + DMA_READ_ADDR_TRIG,
            ctrl=color_lookup_ctrl,
        )

        """ CH:6. Display write DMA --------------------------- """
        px_write_ctrl = self.px_write.pack_ctrl(
            size=1, # 16 bit pixels
            inc_read=False,  # from PIO
            inc_write=True,  # Through display
            # treq_sel=DREQ_PIO1_RX0,
            # chain_to=self.h_scale.channel
        )

        self.px_write.config(
            count=1,
            write=0,    # TBD - display addr
            read=0,     # TBD - palette color
            ctrl=px_write_ctrl
        )

        """ CH:7. Horiz. scale DMA --------------------------- """
        h_scale_ctrl = self.h_scale.pack_ctrl(
            size=2,
            inc_read=True,
            inc_write=False,
            ring_sel=False,  # ring on read
            ring_size=4,    # n bytes = 2^n
            chain_to=self.write_addr.channel,
            treq_sel=DREQ_PIO1_RX0,
            irq_quiet=False
        )

        self.h_scale.config(
            count=1,
            # read=xxx,  # Current horizontal pattern (to be set later)
            write=WRITE_DMA_BASE + DMA_TRANS_COUNT,
            ctrl=h_scale_ctrl
        )
        # self.h_scale.irq(handler=self.irq_h_scale_end)

        """ CH:8. Address Push ------------------- """

        # addr_push_ctrl = self.addr_push.pack_ctrl(
        #     size=2,
        #     treq_sel=DREQ_PIO1_TX1,
        #     inc_read=True,
        #     inc_write=False,
        #     # inc_write=True,
        # )
        #
        # self.addr_push.config(
        #     count=2,
        #     read=addressof(self.value_addrs),
        #     write=PIO1_TX1,
        #     # write=self.debug_bytes1,
        #     ctrl=addr_push_ctrl
        # )
        #
        # if self.debug_dma:
        #     print("~~ DMA CHANNELS in INIT_DMA ~~~~~~~~~~~")
        #     self.debug_dma_and_pio()

    def init_dma_sprite(self, height, width, scaled_height, h_scale=1.0):
        """ Sprite-specific DMA configuration goes here """

        prof.start_profile('scaler.dma_sprite_config')
        self.color_lookup.count = width

        tx_per_row = math.ceil(width / self.px_per_tx)
        self.px_read.count = tx_per_row
        prof.end_profile('scaler.dma_sprite_config')

        prof.start_profile('scaler.h_pattern')
        self.h_scale.read = self.h_patterns[h_scale]
        self.h_scale.count = width
        prof.end_profile('scaler.h_pattern')

        if self.debug_dma:
            print("DMA CONFIG'D for: ")
            print(f"\t h_scale = {h_scale}")
            print(f"\t height / width = {height} / {width}")
            print(f"\t px_per_tx = {self.px_per_tx}")
            print(f"\t tx_per_row = {tx_per_row} (px_read_dma.count)")
            print(f"\t count - color_lookup: {width}")
            print(f"\t h_scale addr:        0x{addressof(self.h_patterns[h_scale]):08X}")
            print(f"\t Scaled height:        {scaled_height}")

            print()
            print("~~ DMA AFTER SPRITE CONFIG ~~~~~~~")
            self.debug_dma_and_pio()

    def irq_row_end(self, ch=None):
        """ DEPRECATED """
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
            pass
            # self.load_and_push_addr_set()

    def irq_ch_end(self, ch):
        ch_name = self.ch_names[ch.channel]
        print(f"  >>> IRQ Channel end: #{ch.channel}. {ch_name}")

    def irq_px_read_end(self, ch):
        if self.read_finished:
            if self.debug_irq:
                print(f"><--- PXREAD END IRQ *FALSE* ---><")
        else:
            if self.debug_irq:
                print(f"<>--- PXREAD END IRQ AFTER {self.rows_read_count} ROWS ---<>")
                self.finish_sprite()

    def irq_h_scale_end(self, ch):
        print(">< >< H SCALE END IRQ REACHED >< ><")

    def is_fifo_full(self):
        return self.sm_read_addr.tx_fifo() == 4

        fifo_status = mem32[PIO1_BASE + PIO_FSTAT]
        fifo_status = fifo_status >> 16 + 1  # Bit #1 is the flag for TX_FULL > SM 1
        fifo_full = fifo_status & 0x0000000F
        fifo_full_sm1 = fifo_full & 0b0000000000000000000000000001
        return fifo_full_sm1

    def load_addr_pair(self, idx):
        # DEPRECATED
        prof.start_profile('scaler.interp_pop')
        new_write = self.value_addrs[idx]
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

        # self.sm_put(new_write)
        # self.sm_put(new_read)

        # self.sm_read_addr.put(new_write)
        # self.sm_read_addr.put(new_read)

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
        # DEPRECATED
        prof.start_profile('scaler.load_addr_pair')
        idx = self.addr_idx
        new_write, new_read = self.load_addr_pair(idx)
        prof.end_profile('scaler.load_addr_pair')

        prof.start_profile('scaler.check_bounds')
        """ check bounds """
        if not new_write or not new_read:
            if self.debug:
                print("~000 ZERO ADDR = NULL TRIGGER 000~")
            self.finish_sprite()
            return False

        if new_write > self.max_write_addr:
            print("** BOUNDS EXCEEDED **")
            self.finish_sprite()
            return False
        prof.end_profile('scaler.check_bounds')

        prof.start_profile('scaler.push_addr_set')
        self.push_addr_set(new_write, new_read)
        prof.end_profile('scaler.push_addr_set')


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
        self.read_addr.active(0)
        self.px_read.active(0)
        self.write_addr.active(0)
        self.color_lookup.active(0)
        self.h_scale.active(0)
        self.sm_read_palette.active(0)
        self.px_write.active(0)

        self.rows_read_count = 0
        self.addr_idx = 0

        # Clear interpolator accumulators
        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0

        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0

    def init_pio(self, palette_addr):
        # self.sm_pixel_skip.restart()
        # self.sm_read_addr.restart()
        self.sm_read_palette.restart()
        self.sm_read_palette.put(palette_addr)

    async def async_start_feed(self):
        print("~~@ IN async_start_feed() @~~")
        asyncio.run(self.async_feed_addresses())

    async def async_feed_addresses(self):
        # DEPRECATED
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
                # self.sm_read_addr.put(new_write)
                # self.sm_read_addr.put(new_read)
                prof.end_profile('scaler.interp_sm_put')

                self.addr_idx += 2
                self.rows_read_count = self.addr_idx

            await asyncio.sleep_ms(10)

