import time
from _rp2 import DMA, StateMachine
from uarray import array
from uctypes import addressof

from images.indexed_image import Image
from scaler.dma_scaler_const import *
from scaler.dma_scaler_pio import pixel_scaler
from scaler.dma_scaling_patterns import ScalingPatterns
from scaler.dma_scaler_debug import ScalerDebugger

ROW_ADDR_DMA_BASE = DMA_BASE_2
ROW_ADDR_TARGET_DMA_BASE = DMA_BASE_3
READ_DMA_BASE = DMA_BASE_4
WRITE_DMA_BASE = DMA_BASE_5

class SpriteScaler():
    def __init__(self, display):
        self.display = display
        self.read_blocks = None
        self.write_blocks = None
        self.value_addrs = None
        self.target_addrs = None

        self.dbg = ScalerDebugger()
        self.debug_bytes1 = self.dbg.get_debug_bytes(byte_size=0, count=16)
        self.debug_bytes2 = self.dbg.get_debug_bytes(byte_size=0, count=16)

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
        self.pattern_dma = DMA()            # 4. Scale pattern
        self.px_read_dma = DMA()            # 5. Sprite data
        self.px_write_dma = DMA()           # 6. Display output

        self.palette = bytearray(512)

        print("About to sm_pixel_scaler")
        # PIO setup
        self.sm_pixel_scaler = StateMachine(
            0, pixel_scaler,
            freq=1_000_000,
        )

        print("About to init_palette_lut")
        self.init_palette_lut()
        self.init_vertical_patterns()

    def draw_sprite(self, sprite:Image, scale_x=1.0, scale_y=1.0):
        """Draw a scaled sprite at the specified position"""
        # Calculate bounds
        scaled_width = int(sprite.width * scale_x)
        scaled_height = int(sprite.height * scale_y)
        print(f"Drawing a sprite of SCALED {scaled_width}x{scaled_height}")

        # Set up vertical control blocks
        base_read = addressof(sprite.pixel_bytes)
        base_write = int(self.display.write_addr + (sprite.y * self.display.width + sprite.x) * 2)

        self.init_v_ctrl_blocks(
            sprite=sprite,
            scale_y=scale_y,
            scaled_height=scaled_height,
            base_read_addr=base_read,
            base_write_addr=base_write
        )

        print(f"About to Init DMA w/ w/h: {sprite.width}x{sprite.height} /// scaled_height: {scaled_height} / scaled_width: {scaled_width}")
        self.init_dma(sprite.height, sprite.width, scaled_height, scaled_width)
        # Add debug prints for DMA configuration
        px_read_ctrl = self.px_read_dma.unpack_ctrl(self.px_read_dma.ctrl)
        print("DMA Configuration:")
        print(f"Pixel read count: {self.px_read_dma.count}")
        print(f"Read increment: {px_read_ctrl['inc_read']}")  # Check INC_READ bit
        print(f"Write increment: {px_read_ctrl['inc_write']}")  # Check INC_WRITE bit

        """ Show key addresses """

        print()
        print("~~ KEY MEMORY ADDRESSES ~~")
        print(f"    ADDRS VALUE ADDR:          0x{addressof(self.value_addrs):08X}")
        print(f"    TARGET ADDRS ADDR:         0x{addressof(self.target_addrs):08X}")
        print(f"    PALETTE ADDR:              0x{addressof(self.palette):08X}")
        print(f"    SPRITE READ BASE ADDR:     0x{base_read:08X}")
        print(f"    DISPLAY WRITE BASE ADDR:   0x{base_write:08X}")
        print()
        print(f"~~ DMA TARGET BLOCKS ~~")
        print(f"0x{self.target_addrs[0]:08x}")
        print(f"0x{self.target_addrs[1]:08x}")

        time.sleep_ms(100)

        print("\n~~ DEBUG BYTES BEFORE DMA ~~")
        self.dbg.print_debug_bytes(self.debug_bytes1, format='bin')
        # self.dbg.print_debug_bytes(self.debug_bytes2, format='bin', num_cols=1)

        # Start the DMA chain
        self.row_addr_target.active(1)
        time.sleep_ms(500)

        print("\n~~ DEBUG BYTES AFTER DMA ~~\n")
        self.dbg.print_debug_bytes(self.debug_bytes1, format='bin')
        # self.dbg.print_debug_bytes(self.debug_bytes2, format='bin', num_cols=1)

        print("\n~~ DMA CHANNELS AFTER ~~~~~~~~~~~\n")
        self.dbg.debug_dma(self.row_addr, "row address", "row_addr", 2)
        self.dbg.debug_dma(self.row_addr_target, "row address target", "row_addr_target", 3)
        self.dbg.debug_dma(self.px_read_dma, "pixel read", "pixel_read", 5)
        self.dbg.debug_dma(self.px_write_dma, "pixel write", "pixel_write", 6)


    def irq_end_row(self, hard):
        print("<===---... IRQ END ROW ...---===>")
        return True

    def init_vertical_patterns(self):
        """Similar to horizontal patterns but for row repeats"""
        v_patterns = {
            # Upscaling
            3.0: [3, 3, 3, 3, 3, 3, 3, 3],  # Triple each row
            2.0: [2, 2, 2, 2, 2, 2, 2, 2],  # Double each row
            1.5: [2, 1, 2, 1, 2, 1, 2, 1],  # Alternating double/single = 1.5x

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

    def init_v_ctrl_blocks(self, sprite, scale_y, scaled_height, base_read_addr, base_write_addr):
        """Create control blocks for vertical scaling"""
        """ @todo: init address calculations using interp, to speed things up """

        """ Testing Upscale / downscale ratios """
        # scale_y = 2
        scale_y = 0.5

        v_pattern = self.v_patterns[scale_y]
        # row_width = (sprite.width) // 2  # Packed pixels
        row_width = 4
        display_stride = self.display.width * 2

        # Separate arrays for read and write control blocks
        # self.read_blocks = array('I', [0] * scaled_height)  # One word per row
        self.read_blocks = []  # One word per row

        self.write_blocks = array('I', [0] * scaled_height)  # One word per row

        self.value_addrs = []
        self.target_addrs = array('I', [0] * 2)

        y_pos = 0
        print(f"Sprite HEIGHT is {scaled_height}")

        for row_idx in range(0, scaled_height):
            # Source sprite reading address
            read_addr = base_read_addr + (row_idx * (row_width))
            count = v_pattern[row_idx % 8]  # Apply vertical scaling pattern

            # count = 1
            print(f"row idx = {row_idx} / row v_count = {count} ")
            print(f"value_addrs array size: {len(self.value_addrs)})")
            print(f"")

            """ For vertical up and downscaling, we repeat the source row 0-x times """
            for rep in range(count):
                # Display writing address
                write_addr = base_write_addr + ((row_idx+rep) * display_stride)

                print(f" R/W {read_addr:08X} / {write_addr:08X}")
                self.value_addrs.append(read_addr) # One for the reader
                self.value_addrs.append(write_addr)# and one for the writer

        self.value_addrs = array('I', self.value_addrs)
        self.read_blocks = array('I', self.read_blocks)
        self.write_blocks = array('I', self.write_blocks)

        print(f"VALUE ADDR POINTER: 0x{addressof(self.value_addrs):08X}")
        print(f"TARGET ADDR POINTER: 0x{addressof(self.target_addrs):08X}")

        """ DEBUG array """
        print("\nVALUE ADDRS: ")
        for i, addr in enumerate(self.value_addrs):
            print(f"#{i}: 0x{addr:08x}")

        """" Add two blocks, one for the pixel reader READ addr, and one for the pixel writer WRITE addr """
        self.target_addrs[0] = int(DMA_BASE_5 + DMA_READ_ADDR_TRIG)
        self.target_addrs[1] = int(DMA_BASE_6 + DMA_READ_ADDR)
        # self.target_addrs[0] = addressof(self.debug_bytes1)
        # self.target_addrs[1] = addressof(self.debug_bytes2)

    def init_dma(self, height, width, scaled_height, scaled_width):
        """Setup the complete DMA chain for sprite scaling"""

        """ CH:2 Row address control DMA """
        row_addr_ctrl = self.row_addr.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=True,  # Through control blocks
            inc_write=False,  # Fixed write target
            # chain_to=self.px_read_dma.channel,  # Chain to pixel reader
        )

        self.row_addr.config(
            count=2,
            read=self.value_addrs,
            # write=PATTERN_DMA_BASE + DMA_READ_ADDR,
            # write=DMA_BASE_5 + DMA_READ_ADDR, # to be changed @ runtime

            ctrl=row_addr_ctrl
        )

        """ CH:3 Row address target DMA """
        row_addr_target_ctrl = self.row_addr_target.pack_ctrl(
            size=2,  # 32-bit control blocks
            inc_read=False,      # Through control blocks
            inc_write=False,
            # ring_sel=0,         # ring on read channel
            # ring_size=1,        # 2 addresses in ring buffer which we'll loop through (read & write)
            chain_to=self.row_addr.channel,
        )

        self.row_addr_target.config(
            count=2,                                    # one addr for read, and one for write
            read=self.target_addrs,          # read/write TARGET address block array
            write=ROW_ADDR_DMA_BASE + DMA_WRITE_ADDR,
            ctrl=row_addr_target_ctrl
        )

        # Pattern DMA (horizontal scale control)
        # pattern_ctrl = self.pattern_dma.pack_ctrl(
        #     size=2,
        #     inc_read=True,
        #     inc_write=True,
        #     ring_sel=1,
        #     ring_size=3,  # 8 entries = 2^3
        #     chain_to=self.px_read_dma.channel
        # )
        #
        # self.pattern_dma.config(
        #     count=8,  # 8-entry patterns
        #     # read=None,  # Current horizontal pattern (to be set later)
        #     # write=WRITE_DMA_BASE + DMA_TRANS_COUNT_TRIG,
        #
        #     ctrl=pattern_ctrl
        # )

        """ 5. Pixel reading DMA --------------------------- """
        px_read_ctrl = self.px_read_dma.pack_ctrl(
            size=2,
            inc_read=True,  # Through sprite data
            inc_write=True,
            chain_to=self.row_addr_target.channel,
            irq_quiet=False
        )

        bytes_per_row = width // 2
        self.px_read_dma.config(
            # count=bytes_per_row*2,
            count=1,
            read=0,  # To be Set per row
            write=self.debug_bytes1,
            ctrl=px_read_ctrl
        )
        # self.px_read_dma.irq(self.irq_end_row, hard=True)

        """ 6. Display write DMA --------------------------- """
        px_write_ctrl = self.px_write_dma.pack_ctrl(
            size=1,
            inc_read=True,  # Through line buffer
            inc_write=True,  # Through display
            # chain_to=self.row_addr_target.channel  # Chain back to v_ctrl
        )

        self.px_write_dma.config(
            count=width,  # One pixel at a time
            read=0,   # To be Set per row
            write=addressof(self.debug_bytes2),
            ctrl=px_write_ctrl
        )

        self.dbg.debug_dma(self.row_addr, "row address", "row_addr", 2)
        self.dbg.debug_dma(self.row_addr_target, "row address target", "row_addr_target", 3)
        self.dbg.debug_dma(self.px_read_dma, "pixel read", "pixel_read", 5)

    def init_palette_lut(self):
        """Initialize the unpacking lookup table"""
        palette = [
            0x0000,  # Example RGB565 values
            0xF800,  # Full red
            0x07E0,  # Full green
            0x001F,  # Full blue
        ]

        palette += [0x0000] * 12

        # For each possible byte value (0-255)
        for byte in range(256):
            # Get high and low pixels
            pixel1 = (byte >> 4) & 0xF
            pixel2 = byte & 0xF

            # Store RGB565 values for both pixels
            self.palette[byte * 2] = palette[pixel1]
            self.palette[byte * 2 + 1] = palette[pixel2]

    def init_row_buffer(self, width):
        # Line buffer for one scaled row of RGB565 pixels
        self.row_buffer = array('H', [0] * width) # 16bit pixels

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

    def close(self):
        """Clean up resources"""
        self.sm_pixel_scaler.active(0)
        self.row_addr.active(0)
        self.pattern_dma.active(0)
        self.px_read_dma.active(0)
        self.px_write_dma.active(0)
