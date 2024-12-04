import math
import time

from array import array
from rp2 import DMA
from machine import mem32, mem8
from uctypes import addressof

from images.indexed_image import Image
from scaler.dma_scaler_const import *
from scaler.dma_scaler_debug import ScalerDebugger
from sprites.sprite import Sprite


class ScalingConfig:
    """Configuration for sprite scaling"""

    def __init__(self, scale_x=1.0, scale_y=1.0):
        self.scale_x = scale_x
        self.scale_y = scale_y
        # Fix: Match original fixed point calculation
        self.fixed_point_bits = 16
        self.step_x = int(65536 / scale_x)  # Original uses this exact calculation
        self.step_y = int(65536 / scale_y)

        # Add validation matching original
        if scale_x <= 0 or scale_y <= 0:
            raise ValueError("Scale must be positive")

class SpriteScaler:
    def __init__(self, display, debug=False):
        self.dbg = ScalerDebugger(None, None, None, None, None)
        self.debug = debug
        self.display = display
        self.screen_width = display.width
        self.screen_height = display.height
        self.debug_bytes = array("H", [0] * 64)  # Increased size for testing
        self.transfers_complete = 0

        """ Debug Buffer """
        self.debug_bytes = array("B", [0xAA] * 256)  # Bigger buffer, pre-filled pattern

        if self.debug:
            print(f"Debug buffer addr: 0x{addressof(self.debug_bytes):08X}")
            print(f"Debug buffer alignment: {addressof(self.debug_bytes) % 2}")

        self._init_dma_channels()

    def _init_dma_channels(self):
        """Initialize DMA channels needed for scaling pipeline"""
        self.read_dma = DMA()   # DMA2
        self.write_dma = DMA()  # DMA3
        self.ctrl_dma = DMA()   # DMA4 - For chaining/control

        self.read_dma_base = DMA_BASE_2
        self.write_dma_base = DMA_BASE_3
        self.ctrl_dma_base = DMA_BASE_4

    # Calculate width and height bits manually
    def calc_bits_needed(self, n):
        bits = 0
        while n > 0:
            n >>= 1
            bits += 1
        return max(1, bits)  # Ensure at least 1 bit

    def _conf_interp_read(self, sprite: Image, config: ScalingConfig):
        """Configure INTERP0 for sprite coordinate generation"""
        # Base sprite dimensions
        sprite_width = sprite.width
        sprite_height = sprite.height

        # Configure base registers
        # mem32[INTERP0_BASE0] = config.step_x  # X step size
        mem32[INTERP0_BASE0] = 0x00100000  # X step size

        # mem32[INTERP0_BASE1] = config.step_y  # Y step size
        mem32[INTERP0_BASE1] = 0x00010000  # Y step size
        mem32[INTERP0_BASE2] = addressof(sprite.pixel_bytes)  # Sprite data base

        scaled_width = int(sprite.width * config.scale_x)
        scaled_height = int(sprite.height * config.scale_y)

        width_bits = self.calc_bits_needed(scaled_width)
        height_bits = self.calc_bits_needed(scaled_height)

        # Each byte contains two 4-bit indices
        bytes_per_row = (scaled_width + 1) // 2  # Round up

        if self.debug:
            print(f"    Bytes per row: {bytes_per_row}")
            print(f"    Sprite original size:   {sprite_width}x{sprite_height}")
            print(f"    Sprite scaled:          {scaled_width}x{scaled_height}")
            print(f"    Width bits: {width_bits}, Height bits: {height_bits}")

        # Configure lane 0 for X coordinates
        lane0 = (
                (16 << 0) |     # SHIFT: 16 fixed point bits
                (0 << 5) |      # MASK_LSB: start at 0
                (15 << 10) |  # MASK_MSB: changed from 3 to 15 for larger range
                (1 << 17) |     # ADD_RAW: enable raw accumulator
                (1 << 18)       # FORCE_MSB: critical for address generation
        )

        # Configure lane 1 for Y coordinates
        lane1 = (
                (16 << 0) |  # SHIFT: 16 fixed point bits
                (4 << 5) |  # MASK_LSB: starts after X bits (4)
                (7 << 10) |  # MASK_MSB: 4 bits for Y range
                (1 << 16) |  # CROSS_INPUT: use other accumulator
                (1 << 17) |  # ADD_RAW: enable raw accumulator
                (1 << 18)  # FORCE_MSB: critical for address generation
        )


        # Set control registers
        # mem32[INTERP0_CTRL_LANE0] = lane0
        mem32[INTERP0_CTRL_LANE0] = 0x00063C10
        # mem32[INTERP0_CTRL_LANE1] = lane1
        mem32[INTERP0_CTRL_LANE1] = 0x00071C90

        # Clear state first
        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0

        if self.debug:
            print()
            print(f"INTERP0 Config:")
            print("----------------------")
            print(f"CTRL0: 0x{lane0:08X}")
            print(f"CTRL1: 0x{lane1:08X}")
            print(f"BASE0: 0x{config.step_x:08X}")
            print(f"BASE1: 0x{config.step_y:08X}")
            print(f"BASE2: 0x{mem32[INTERP0_BASE2]:08X}")
            print()

    def _configure_write(self, x: int, y: int, width: int, height: int):
        """Configure INTERP1 for framebuffer addressing"""
        # Fix: Match original framebuffer calculations
        fb_addr = self.display.write_addr + (y * self.screen_width + x) * 2

        # Fix: Original control register values
        ctrl0 = (
                (0 << 0) |  # No shift for X
                (0 << 5) |  # No mask LSB
                (15 << 10) |  # Prevent overflow
                (1 << 17)  # ADD_RAW for direct increment
        )

        ctrl1 = (
                (1 << 0) |  # Shift by 1 for 16-bit pixels
                (0 << 5) |  # No mask LSB
                (15 << 10) |  # Prevent overflow
                (1 << 17)  # ADD_RAW for stride
        )

        mem32[INTERP1_CTRL_LANE0] = ctrl0
        mem32[INTERP1_CTRL_LANE1] = ctrl1
        mem32[INTERP1_ACCUM0] = 0
        mem32[INTERP1_ACCUM1] = 0
        mem32[INTERP1_BASE0] = 2  # 16-bit pixels
        mem32[INTERP1_BASE1] = self.screen_width * 2  # Full stride
        mem32[INTERP1_BASE2] = fb_addr

    def _scale_sprite_span(self, sprite_data, count, sprite, scaled_width):
        """Original helper for testing/validation

        Args:
            sprite_data: Source sprite pixel data
            count: Total number of pixels to output
            sprite: Sprite object with width/height
            scaled_width: Width after scaling

        Returns:
            bytearray of scaled pixel data
        """
        output = bytearray(count)
        step_fixed = int(65536 * (sprite.width / scaled_width))

        curr_y = 0
        curr_x_fixed = 0

        for i in range(count):
            x_pos = curr_x_fixed >> 16
            x_pos = min(x_pos, sprite.width - 1)

            byte_addr = x_pos + (curr_y * sprite.width)
            output[i] = sprite_data[byte_addr]

            curr_x_fixed += step_fixed
            if (i + 1) % scaled_width == 0:
                curr_y = (curr_y + 1) % sprite.height
                curr_x_fixed = 0

        return output

    def draw_sprite(self, sprite, x: int, y: int, config: ScalingConfig = None):

        self.dbg.debug_dma(self.read_dma, "READ", "draw_sprite_start", 2)

        """Draw a scaled sprite to the display"""
        if config is None:
            config = ScalingConfig()

        # Calculate dimensions
        scaled_width = max(1, math.ceil(sprite.width * config.scale_x))
        scaled_height = max(1, math.ceil(sprite.height * config.scale_y))

        print()
        print(f"~~ Drawing a sprite of {scaled_width}x{scaled_height} ~~")

        # Validate boundaries
        if (x + scaled_width > self.screen_width or
                y + scaled_height > self.screen_height):
            raise ValueError("Scaled sprite would exceed screen bounds")

        self._conf_interp_read(sprite, config)
        # self._configure_write(x, y, scaled_width, scaled_height)
        # self._setup_dma_transfer(sprite, config, x, y)

        self.test_sio_dma()
        # Run benchmark with different durations
        # self.sio_dma_speed_test(self.read_dma)

        # for duration in [100, 500, 1000]:
        #     reads = self.benchmark_sio_reads(duration)

        # self.dbg.debug_dma(self.read_dma, "READ", "sprite_scaler_before_active", 2)

        # self.read_dma.active(1)

        # self.dbg.debug_dma(self.read_dma, "READ", "sprite_scaler_after_active", 2)

        # After DMA config
        print("Starting transfer...")
        # self.write_dma.active(1)
        last_loop = start_time = time.ticks_ms()

        while True:
            if time.ticks_diff(time.ticks_ms(), last_loop) > 20:
                print()

                """ Show DMA debug """
                print()

                # Check DMA status
                busy = mem32[self.read_dma_base + DMA_AL1_CTRL] & (1 << 24)
                if not busy:
                    print("Transfer complete!")
                    break
                print("Transfer ongoing...")

                last_loop = time.ticks_ms()

        self.dbg.debug_dma(self.read_dma, "READ", "after_loop", 2)

        # self.show_debug_buffer()

    def _debug_print_pattern(self, output, scaled_width, scaled_height):
        """Match original debug output exactly"""
        print("\nOutput pattern:")
        for r in range(scaled_height):
            print("")
            for c in range(scaled_width):
                idx = r * scaled_width + c
                print(f"{output[idx]:08b} ", end="")
                if c > 2 and not (c % scaled_width):
                    print()
            print()

    def test_sio_dma(self):
        # Debug address calculation
        print(f"SIO_BASE: 0x{SIO_BASE:08X}")
        # INTERP0_POP_FULL
        # read_addr = SIO_BASE + 0x004
        read_addr = SIO_BASE + INTERP0_POP_FULL

        # Timer low count register
        # TIMER_BASE = 0x40054000
        # TIMER_RAWL = TIMER_BASE + 0x28  # TIMERAWL offset
        # read_addr = TIMER_RAWL

        print(f"Calculated read addr: 0x{read_addr:08X}")


        # Try reading a simple SIO register like GPIO_IN
        read_ctrl = self.read_dma.pack_ctrl(
            size=2,  # 32-bit transfers
            inc_write=0,
            inc_read=0,
        )

        self.read_dma.config(
            count=1,
            # read=SIO_BASE + 0x004,  # GPIO_IN register
            read=read_addr,
            write=self.debug_bytes,
            ctrl=read_ctrl
        )

    def benchmark_sio_reads(self, duration_ms=1000):
        count = 0
        start_time = time.ticks_ms()
        end_time = time.ticks_add(time.ticks_ms(), duration_ms)
        addr = INTERP0_POP_FULL

        print(f"\n--- INTERP --- ({addr:08X})\n")
        while time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
            _ = mem32[addr]
            # print(f"\t{_:08X}")
            count += 1

        interval = time.ticks_diff(time.ticks_ms(), start_time)
        reads_per_sec = (count * 1000) // interval

        print(f"Duration {duration_ms} ms: count: {count:,} {reads_per_sec:,} reads/second")

        return reads_per_sec

    def sio_dma_speed_test(self, mydma):
        # Test buffer
        test_buf = array('I', [0] * 16)

        dma = mydma
        read_ctrl = dma.pack_ctrl(
            size=2,  # 32-bit reads
            inc_write=1,
            inc_read=0,
        )

        # Configure DMA read from INTERP0_POP_FULL
        dma.config(
            count=16,
            read=INTERP0_BASE1,  # INTERP0_POP_FULL
            write=test_buf,
            ctrl=read_ctrl
        )

        # Start transfer
        dma.active(1)

        # Print results
        print("Buffer contents:")
        for i in range(16):
            print(f"{test_buf[i]:08x}")

    def setup_scaling_dma(self):
        # Channel 0: Pattern reader
        self.pattern_dma = DMA()
        pattern_ctrl = self.pattern_dma.pack_ctrl(
            size=2,  # 32-bit transfers
            inc_read=1,  # Increment through pattern
            inc_write=0,  # Write to same trigger register
            ring_size=3,  # 2^3 = 8 entries
            ring_sel=1  # Wrap read address
        )

        # Channel 1: Sprite data reader
        read_ctrl = self.read_dma.pack_ctrl(
            size=1,  # 8-bit transfers (sprite data)
            inc_read=1,  # Increment through sprite
            inc_write=1  # Write to line buffer
        )

        # Channel 2: Display writer
        write_ctrl = self.write_dma.pack_ctrl(
            size=1,  # 8-bit transfers
            inc_read=0,  # Read same pixel multiple times
            inc_write=1  # Increment display position
        )

        # Chain them together:
        # Pattern -> Controls Read -> Controls Write
        self.pattern_dma.chain_to(self.read_dma)
        self.read_dma.chain_to(self.write_dma)

    def _dma_complete(self, dma):
        """IRQ handler for DMA completion"""
        if self.debug:
            print("DMA transfer complete")

        # Clear interrupt
        dma.clear_irq()

        # Update any statistics/state
        self.transfers_complete += 1

    def show_debug_buffer(self):
        print(f"\nDebug Buffer Contents:")
        rows = 8  # Show more rows
        cols = 8

        for r in range(rows):
            row_str = ""
            for c in range(cols):
                idx = r * cols + c
                if idx < len(self.debug_bytes):
                    val = self.debug_bytes[idx]
                    row_str += f"{val:02X} "  # Show just byte values
            print(row_str)

    def get_debug_bytes(self):
        debug_bytes = self.debug_bytes

        for i in range(len(debug_bytes)):
            debug_bytes[i] = 0xAA if i % 2 else 0x55

        return debug_bytes

    def test_interp0(self):
        """Debug interpolator output in detail"""
        print("\nDetailed INTERP0 test:")

        # Test raw output
        val_full = mem32[INTERP0_POP_FULL]
        val_lane0 = mem32[INTERP0_POP_LANE0]
        val_lane1 = mem32[INTERP0_POP_LANE1]

        print(f"FULL value: 0x{val_full:08X}")
        print(f"LANE0 value: 0x{val_lane0:08X}")
        print(f"LANE1 value: 0x{val_lane1:08X}")

        # Try reading the calculated address
        addr = mem32[INTERP0_BASE2] + (val_full & 0xFF)
        data = mem8[addr]  # Read byte from calculated address
        print(f"Data at addr 0x{addr:08X}: 0x{data:02X}")

        # Reset accumulators
        mem32[INTERP0_ACCUM0] = 0
        mem32[INTERP0_ACCUM1] = 0