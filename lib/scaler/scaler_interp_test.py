import sys
import time

import math
from rp2 import DMA
from machine import mem32
from uctypes import addressof

from scaler.dma_scaler_const import *
from scaler.dma_scaler_debug import ScalerDebugger
from scaler.sprite_scaler_test import test_sprite_scaling
from screens.screen import Screen

"""
NOTE: the interpolator does NOT work with DMA, since they are not connected to the same bus, 
so all of the below is futile

"""

class InterpTestScreen(Screen):
    sprite_width: int
    sprite_height: int
    screen_width: int
    screen_height: int

    def __init__(self, display):
        self.screen_width = display.width
        self.screen_height = display.height
        self.sprite_width = 4
        self.sprite_height = 4

        self.write_addr = display.write_addr
        self.display = display
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

        # self.init_interpolator(palette_addr, sprite_addr, fb_addr)

    def init_interpolator(self, sprite_data, scale):
        # For byte-aligned sprite data
        sprite_width_bits = int(math.log2(self.sprite_width))

        # Calculate step size in fixed point (16.16)
        # For downscaling, step needs to be larger; for upscaling, smaller
        step = int(65536 / scale)  # Fixed point step

        uv_fractional_bits = 16

        ctrl0 = (
                (16 << 0) |  # SHIFT
                (0 << 5) |  # MASK_LSB start
                (3 << 10) |  # MASK_MSB - changed to grab 4 bits for 0-3 range
                (1 << 17) |  # ADD_RAW
                (1 << 18)  # FORCE_MSB
        )

        ctrl1 = (
                (16 << 0) |
                (4 << 5) |  # MASK_LSB starts after X bits
                (7 << 10) |  # MASK_MSB - 4 bits for Y also
                (1 << 16) |  # CROSS_INPUT
                (1 << 17) |  # ADD_RAW
                (1 << 18)  # FORCE_MSB
        )

        mem32[INTERP0_CTRL_LANE0] = ctrl0
        mem32[INTERP0_CTRL_LANE1] = ctrl1

        # Base registers
        mem32[INTERP0_BASE0] = 2    # X increment (one byte at a time)
        mem32[INTERP0_BASE1] = step    # Row stride (bytes per row)
        mem32[INTERP0_BASE2] = addressof(sprite_data)

    def init_fb_interpolator(self, x=0, y=0):
        """Configure INTERP1 for framebuffer addressing

        Args:
            x: Screen X coordinate
            y: Screen Y coordinate
            scaled_width: Width of scaled sprite
            scaled_height: Height of scaled sprite
        """
        # Calculate base framebuffer address for sprite position
        fb_base = self.write_addr + (y * self.screen_width + x) * 2

        # Configure lane 0 for X position handling
        ctrl0 = (
                (0 << 0) |  # No shift needed for direct addressing
                (0 << 5) |  # No mask LSB - we want full values
                (15 << 10) |  # Mask MSB to prevent overflow
                (1 << 17) |  # ADD_RAW for direct increment
                (0 << 18)  # Don't force MSB
        )

        # Configure lane 1 for Y position handling
        ctrl1 = (
                (1 << 0) |  # Shift by 1 to account for 16-bit pixels
                (0 << 5) |  # No mask LSB
                (15 << 10) |  # Mask MSB to prevent overflow
                (0 << 16) |  # No cross input
                (1 << 17) |  # ADD_RAW for direct increment
                (0 << 18)  # Don't force MSB
        )

        # Set up interpolator registers
        mem32[INTERP1_CTRL_LANE0] = ctrl0
        mem32[INTERP1_CTRL_LANE1] = ctrl1

        # BASE0: Pixel increment (2 bytes per pixel)
        mem32[INTERP1_BASE0] = 2

        # BASE1: Row stride in bytes
        mem32[INTERP1_BASE1] = self.screen_width * 2

        # BASE2: Framebuffer base address
        mem32[INTERP1_BASE2] = fb_base

        # Initialize accumulators
        mem32[INTERP1_ACCUM0] = 0  # Start at first pixel
        mem32[INTERP1_ACCUM1] = 0  # Start at first row

    def _scale_sprite_span(self, sprite_data, x, y, dx, dy, count):
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

    def scale_sprite_span(self, sprite_data, scale):
        output_width = max(1, math.ceil(self.sprite_width * scale))
        output_height = max(1, math.ceil(self.sprite_height * scale))
        bytesize = output_width * output_height
        output = bytearray(bytesize)

        for pixel_index in range(bytesize):
            # Integer division by scale gives us proper pixel repetition
            curr_y = (pixel_index // output_width) // scale
            curr_x = (pixel_index % output_width) // scale

            # Clamp to source boundaries
            curr_x = min(curr_x, self.sprite_width - 1)
            curr_y = min(curr_y, self.sprite_height - 1)

            offset = int(curr_y * self.sprite_width + curr_x)
            output[pixel_index] = sprite_data[offset]

        return output

    def sprite_scaling_demo(self):
        test_sprite_scaling(self.display)
        return

        start_x = 0
        start_y = 0

        """ Test the scaler using different scale factors, both upscale and downscale """
        for scale in [0.12, 0.25, 0.5, 0.75, 0.80, 1, 1.2, 1.5, 2, 3, 4]:
        # for scale in [1, 2, 3, 4]:
            print()
            print()
            print(f"\n=== Testing {scale * 100}% scaling ===")

            # Calculate scaled width
            scaled_width = max(1, math.ceil(self.sprite_width * scale))
            scaled_height = max(1, math.ceil(self.sprite_height * scale))

            # self.init_interpolator(sprite_data, scale) # @TODO: add independent horiz and vert scaling
            # self.init_fb_interpolator(self.screen_width)
            self.out_addr = self.write_addr + (start_y * self.screen_width + start_x) * 2

            # Calculate output size based on scale
            output = self.scale_sprite_span(sprite_data, scale)

            # Print results with proper line breaks
            print()
            print()
            print("\nOutput pattern:")

            for r in range(scaled_height):
                print("")
                for c in range(scaled_width):
                    idx = int(r * scaled_width + c)
                    print(f"{output[idx]:08b} ", end="")

                    if c > 2 and not (c % (scaled_width)):
                        print()

            print("\n")
            print()
            print()

    def _setup_dma_transfer(self, sprite: Sprite, config: ScalingConfig):
        """Set up and start DMA transfer chain"""
        scaled_width = int(sprite.width * config.scale_x)
        scaled_height = int(sprite.height * config.scale_y)

        # Configure read channel
        read_config = (
                (0 << 0) |  # increment read
                (0 << 1) |  # increment write
                (DMA_SIZE_16 << 2) |  # transfer size
                (0 << 4) |  # read increment
                (0 << 5) |  # write increment
                (self.write_dma.channel_id << 11)  # chain to write channel
        )

        mem32[self.read_dma.base + DMA_READ_ADDR] = INTERP0_POP_FULL
        mem32[self.read_dma.base + DMA_WRITE_ADDR] = INTERP1_ACCUM0
        mem32[self.read_dma.base + DMA_TRANS_COUNT] = scaled_width
        mem32[self.read_dma.base + DMA_CTRL_TRIG] = read_config

        # Configure write channel
        write_config = (
                (0 << 0) |  # increment read
                (1 << 1) |  # increment write
                (DMA_SIZE_16 << 2) |  # transfer size
                (0 << 4) |  # read increment
                (1 << 5) |  # write increment
                (1 << 15)  # enable
        )

        mem32[self.write_dma.base + DMA_READ_ADDR] = INTERP1_POP_FULL
        mem32[self.write_dma.base + DMA_WRITE_ADDR] = self.display.write_addr
        mem32[self.write_dma.base + DMA_TRANS_COUNT] = scaled_width

        # Writing to CTRL_TRIG starts the channel
        mem32[self.write_dma.base + DMA_CTRL_TRIG] = write_config

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
