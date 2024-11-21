import sys
import time

import math
from rp2 import DMA
from machine import mem32
from uctypes import addressof

from scaler.dma_scaler_const import *
from scaler.dma_scaler_debug import ScalerDebugger
from screens.screen import Screen


class InterpTestScreen(Screen):
    sprite_width: int
    sprite_height: int
    screen_width: int
    screen_height: int

    def __init__(self, display):
        self.screen_width = display.width
        self.screen_height = display.height
        self.write_addr = display.write_addr
        self.dbg = ScalerDebugger(None, None, None, None, None)

        self.sprite_scaling_demo()
        sys.exit(1)

        read_chan = DMA()       # 2
        palette_chan = DMA()    # 3
        write_chan = DMA()      # 4

        width = 32
        self.configure_palette_dma(read_chan, palette_chan, write_chan,
                              0, 0, width)

    def show(self, sprite, x=0, y=0):
        # Address setup
        palette_addr = addressof(sprite.palette_bytes)
        sprite_addr = addressof(sprite.pixel_bytes)
        fb_addr = self.write_addr + (y * self.display.width + x) * 2

        self.init_interpolator(palette_addr, sprite_addr, fb_addr)

    def test_interp_out(self):
        """ Learning how the interpolators work, for the most part """
        image_width = 8
        image_height = 8

        # Set up row strides
        sprite_stride = image_width // 2  # 2px per input byte
        screen_stride = self.screen_width * 2 # 16 bit screen output


        # Set increment amounts
        # mem32[INTERP0_BASE0] = sprite_stride
        # mem32[INTERP0_BASE1] = screen_stride

        base_addr = 0x20000000
        fb_addr =   0x50000000

        # Initialize accumulators with base addresses
        mem32[INTERP0_ACCUM0] = base_addr
        mem32[INTERP0_ACCUM1] = fb_addr

        # Configure lane 0
        mem32[INTERP0_CTRL_LANE0] = (
                1 << 0 |  # Shift 1
                1 << 4 |  # No LSB mask
                0 << 8 |  # No MSB mask
                1 << 12 |  # signed
                1 << 17 |  # ADD_RAW
                1 << 18 |  # FORCE_MSB
                1 << 19  # ADD_BEFORE
        )

        # Configure lane 1
        mem32[INTERP0_CTRL_LANE1] = (
                1 << 0 |  # Shift 1
                1 << 4 |  # No LSB mask
                0 << 8 |  # No MSB mask
                1 << 12 |  # signed
                1 << 17 |  # ADD_RAW
                1 << 18 |  # FORCE_MSB
                1 << 19  # ADD_BEFORE
        )

        for i in range(image_height):
            new_addr1 = mem32[INTERP0_POP_LANE1]
            new_addr2 = mem32[INTERP0_POP_LANE0]
            print(f"{i} - read row addr: 0x{new_addr1:08X} - 0x{new_addr2:08X} ")

    def init_interpolator(self, sprite_data, scale_factor=0.5):
        self.sprite_width = 4
        self.sprite_height = 4

        # Calculate scaled width
        self.scaled_width = max(1, int(self.sprite_width * scale_factor))

        # For byte-aligned data
        sprite_width_bits = 2  # log2(4) for byte positions
        uv_fractional_bits = 16

        # Lane configuration remains the same as it handles the base addressing
        ctrl0 = (
                (uv_fractional_bits << 0) |  # SHIFT
                (0 << 5) |  # MASK_LSB
                (1 << 10) |  # MASK_MSB for byte positions
                (1 << 17)  # ADD_RAW
        )

        ctrl1 = (
                ((uv_fractional_bits - 2) << 0) |  # SHIFT adjusted for bytes
                (2 << 5) |  # MASK_LSB = width_bits
                (3 << 10) |  # MASK_MSB for row indexing
                (1 << 17)  # ADD_RAW
        )

        mem32[INTERP0_CTRL_LANE0] = ctrl0
        mem32[INTERP0_CTRL_LANE1] = ctrl1

        # Base registers
        mem32[INTERP0_BASE0] = 1  # X increment (one byte at a time)
        mem32[INTERP0_BASE1] = 4  # Row stride (bytes per row)
        mem32[INTERP0_BASE2] = addressof(sprite_data)

    def scale_sprite_span(self, sprite_data, x, y, dx, dy, count):
        # Calculate step size in fixed point (16.16)
        step_fixed = int(65536 * (self.sprite_width / self.scaled_width))

        output = bytearray(count)
        pixels_per_row = self.sprite_width

        print(f"\nScaling Configuration:")
        print(f"Original width: {self.sprite_width}")
        print(f"Scaled width: {self.scaled_width}")
        print(f"Step (fixed point): 0x{step_fixed:08x}")

        curr_y = 0
        curr_x_fixed = 0  # Use fixed point for x position

        for i in range(count):
            # Calculate current x position
            x_pos = curr_x_fixed >> 16

            # Ensure we don't exceed sprite width
            x_pos = min(x_pos, self.sprite_width - 1)

            # Calculate byte address
            byte_addr = x_pos + (curr_y * pixels_per_row)

            # Get the byte
            pixel = sprite_data[byte_addr]
            output[i] = pixel

            # Debug output
            # print(f"\nStep {i}:")
            # print(f"  X_fixed: 0x{curr_x_fixed:08x} -> pos: {x_pos}")
            # print(f"  Row: {curr_y}, Byte addr: {byte_addr}")
            # print(f"  Pixel: 0b{pixel:08b}")

            # Update position
            curr_x_fixed += step_fixed

            # Move to next row when we've output scaled_width pixels
            if (i + 1) % self.scaled_width == 0:
                curr_y = (curr_y + 1) % self.sprite_height
                curr_x_fixed = 0

        return output

    def sprite_scaling_demo(self):
        print("Sprite scaling demo (with wrap):")

        sprite_data = bytearray([
            0b00000001, 0b00000011, 0b00000111, 0b00001111,  # Row 0
            0b00000001, 0b00000011, 0b00000111, 0b00001111,  # Row 1
            0b00000001, 0b00000011, 0b00000111, 0b00001111,  # Row 2
            0b00000001, 0b00000011, 0b00000111, 0b00001111,  # Row 3
        ])

        # Test different scale factors
        for scale in [0.12, 0.25, 0.5, 0.75, 0.80, 1, 1.2, 1.5, 2, 3, 4]:
            print()
            print()
            print(f"\n=== Testing {scale * 100}% scaling ===")
            self.init_interpolator(sprite_data, scale_factor=scale) # @TODO: add independent horz and vert scaling

            # Calculate output size based on scale
            output_size = self.scaled_width * self.sprite_height
            output = self.scale_sprite_span(sprite_data, 0, 0, 0, 0, output_size)

            # Print results with proper line breaks
            print("\nOutput pattern:")
            for r in range(self.sprite_height):
                print("")
                for c in range(self.scaled_width):
                    idx = r * self.scaled_width + c
                    print(f"{output[idx]:08b} ", end="")
                    if c > 2 and not (c % ((self.scaled_width // 2) - 1)):
                        print("")

            print("\n")
            print()
            print()

    def configure_palette_dma(self, read_chan, palette_chan, write_chan,
                              source_addr, dest_addr, width):
        """
        read_chan: DMA channel for reading source indices
        palette_chan: DMA channel for palette lookup
        write_chan: DMA channel for writing to destination
        source_addr: Address of 4-bit indexed source data
        dest_addr: Final output address
        width: Number of pixels to process
        """

        # Channel 1: Source data -> PIO
        read_config = dma_channel_get_default_config(read_chan)
        channel_config_set_transfer_data_size(read_config, DMA_SIZE_32)  # 32-bit reads
        channel_config_set_read_increment(read_config, True)
        channel_config_set_dreq(read_config, pio_get_dreq(pio0, sm0, True))

        dma_channel_configure(
            read_chan,
            read_config,
            pio0.txf[sm0],  # Write to PIO TX FIFO
            source_addr,  # Read from source
            (width + 7) // 8,  # Number of 32-bit words (8 pixels per word)
            False
        )

        # Channel 2: PIO -> Palette Lookup
        palette_config = dma_channel_get_default_config(palette_chan)
        channel_config_set_transfer_data_size(palette_config, DMA_SIZE_8)  # 8-bit for 4-bit indices
        channel_config_set_read_increment(palette_config, False)
        channel_config_set_dreq(palette_config, pio_get_dreq(pio0, sm0, False))

        dma_channel_configure(
            palette_chan,
            palette_config,
            INTERP1_ACCUM1,  # Write index to interpolator
            pio0.rxf[sm0],  # Read from PIO RX FIFO
            width,  # One per pixel
            False
        )

        # Channel 3: Read palette data and write to destination
        write_config = dma_channel_get_default_config(write_chan)
        channel_config_set_transfer_data_size(write_config, DMA_SIZE_16)  # 16-bit color
        channel_config_set_read_increment(write_config, True)
        channel_config_set_write_increment(write_config, True)

        dma_channel_configure(
            write_chan,
            write_config,
            dest_addr,  # Write to destination
            INTERP1_POP_LANE0,  # Read from interpolator (computed address)
            width,  # One per pixel
            True  # Start the chain
        )
