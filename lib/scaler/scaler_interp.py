import machine
from rp2 import DMA
from uctypes import addressof
from scaler.dma_scaler_const import *
from scaler.dma_scaler_pio import *
from scaler.scaler_interp_pio import indexed_sprite_handler


class SpriteScaler:
    def __init__(self, display, sm, dma_out, debug=None):
        self.display = display
        self.write_addr = self.display.write_addr

        self.sm = sm
        self.dbg = debug
        self.debug_bytes = True
        self.dma_out = dma_out

        self.freq = 10 * 1000
        self.finished = False

        # Init interpolators
        self.init_interpolators()
        self.init_pio()
        self.init_dma()

    def init_interpolators(self):
        if self.dbg:
            print("\n=== Interpolator Setup ===")
            print(f"INTERP0 before: 0x{machine.mem32[INTERP0_CTRL_LANE0]:08X}")

        # Position interpolator config
        machine.mem32[INTERP0_CTRL_LANE0] = (
                8 << 0 |  # 8.8 fixed point
                0 << 4 |  # No LSB mask
                7 << 8 |  # 8-bit MSB mask
                0 << 12 |  # Unsigned
                1 << 20  # Cross input
        )

        # Clear accumulators
        machine.mem32[INTERP0_BASE0] = 0
        machine.mem32[INTERP0_BASE1] = 0
        machine.mem32[INTERP0_BASE2] = 0

        if self.dbg:
            print(f"INTERP0 after: 0x{machine.mem32[INTERP0_CTRL_LANE0]:08X}")

        # Color interpolator
        machine.mem32[INTERP1_CTRL_LANE0] = (
                1 << 0 |  # ×2 for 16-bit colors
                0 << 4 |  # No mask
                3 << 8 |  # 4-bit indices
                0 << 12 |  # Unsigned
                1 << 20  # Cross input
        )

        if self.dbg:
            print(f"INTERP1: 0x{machine.mem32[INTERP1_CTRL_LANE0]:08X}")

    def init_pio(self):
        """ Interpolator all-in-one """
        # debug_pin = Pin(9, Pin.OUT)  # Choose unused pin for debug output

        sm_indexed_scaler = self.sm
        sm_indexed_scaler.init(
            indexed_sprite_handler,
            freq=self.freq,  # Slow down for debugging
            set_base=10,  # Using GPIO 10-17
            in_base=10,
            out_base=10,
            sideset_base=9  # Debug pin
        )

    def init_dma(self):
        """ Pixel out channel (Debugging) --------------------------------------- """
        if self.debug_bytes:
            self.debug_bytes = self.dbg.get_debug_bytes()
            write =  addressof(self.debug_bytes)
        else:
            write = addressof(self.debug_bytes)


        dma_out_ctrl = self.dma_out.pack_ctrl(
            size=2,
            inc_read=False,
            inc_write=True,
            treq_sel=DREQ_PIO1_RX0,
            chain_to=self.dma_out.channel,
        )
        self.dma_out.config(
            count=1000,
            read=PIO1_RX0,
            write=write,
            ctrl=dma_out_ctrl,
        )

    def set_scale(self, h_scale, v_scale):
        # Convert to 8.8 fixed point
        h_fixed = int(h_scale * 256)
        v_fixed = int(v_scale * 256)

        # Configure interpolators
        machine.mem32[INTERP0_BASE0] = h_fixed
        machine.mem32[INTERP0_BASE1] = v_fixed

        # Set strides
        machine.mem32[INTERP0_BASE1] = self.display.width // 2  # 4-bit packed
        machine.mem32[INTERP1_BASE1] = self.display.width * 2  # 16-bit out

    def draw_scaled_sprite(self, sprite, x=0, y=0, h_scale=1.0, v_scale=1.0):
        """Draw scaled sprite using hardware interpolation

        Args:
            sprite: Image with pixel_bytes and palette_bytes
            x, y: Destination coordinates
            scale_x, scale_y: Scale factors (0.5-4.0)
        """
        if self.dbg:
            self.dbg.debug_sm_pins(self.sm)

            print("\n=== Starting Sprite Draw ===")
            print(f"Position: ({x}, {y})")
            print(f"Scale: ({h_scale}x, {v_scale}x)")
            print(f"Sprite: {sprite.width}x{sprite.height} ({len(sprite.pixel_bytes)} bytes)")

            # Show more sprite data bytes
            print("\nSprite data (first 16 bytes, unpacked indices):")
            for i in range(min(16, len(sprite.pixel_bytes))):
                byte = sprite.pixel_bytes[i]
                idx1 = byte >> 4  # High nibble
                idx2 = byte & 0x0F  # Low nibble
                print(f"Byte {i:2d}: 0x{byte:02x} -> [{idx1},{idx2}]")

        # Scale setup
        h_fixed = int(h_scale * 256)
        v_fixed = int(v_scale * 256)
        machine.mem32[INTERP0_BASE0] = h_fixed
        machine.mem32[INTERP0_BASE1] = v_fixed

        if self.dbg:
            print(f"\n=== Scale Configuration ===")
            print(f"H fixed: 0x{h_fixed:08X}")
            print(f"V fixed: 0x{v_fixed:08X}")

        # Step calculation
        row_step = self.display.width // 2
        out_step = self.display.width * 2
        machine.mem32[INTERP0_BASE1] = row_step
        machine.mem32[INTERP1_BASE1] = out_step

        if self.dbg:
            print(f"\n=== Address Steps ===")
            print(f"Row step: {row_step} bytes")
            print(f"Out step: {out_step} bytes")
            print(f"Display width: {self.display.width}")

        # Address setup
        palette_addr = addressof(sprite.palette_bytes)
        sprite_addr = addressof(sprite.pixel_bytes)
        fb_addr = self.write_addr + (y * self.display.width + x) * 2

        if self.dbg:
            print("---------------------------")
            print("\nPalette contents:")
            for i in range(min(16, len(sprite.palette_bytes)) // 2):
                color = sprite.palette_bytes[i * 2] << 8 | sprite.palette_bytes[i * 2 + 1]
                r = (color >> 11) & 0x1F
                g = (color >> 5) & 0x3F
                b = color & 0x1F
                print(f"Color {i:2d}: 0x{color:04x} (R:{r:2d} G:{g:2d} B:{b:2d})")

                print(f"\n=== Memory Map ===")
                print(f"Palette: 0x{palette_addr:08X}")
                print(f"Sprite:  0x{sprite_addr:08X}")
                print(f"FB:      0x{fb_addr:08X}")

            # Verify palette data
            print("\nPalette data check:")
            for i in range(min(8, len(sprite.palette_bytes)) // 2):
                val = sprite.palette_bytes[i * 2] << 8 | sprite.palette_bytes[i * 2 + 1]
                print(f"Color {i}: 0x{val:04X}")

            # Verify sprite data
            print("\nSprite data:")
            for i in range(min(64, len(sprite.pixel_bytes))):
                print(f"0x{sprite.pixel_bytes[i]:02X}\t")

            print("\nPre-transfer SM state:")
            self.dbg.debug_pio_status()
            self.dbg.debug_register()

        # start DMA
        self.dma_out.active(1)

        # Start transfer
        self.sm.active(0)

        if self.dbg:
            print("\n=== Starting Transfer ===")

        self.sm.put(palette_addr)
        self.sm.put(sprite_addr)
        self.sm.put(fb_addr)

        self.sm.active(1)

        # Monitor execution
        while not self.sm.irq():
            if self.dbg:
                print("\nTransfer in progress:")
                self.dbg.debug_pio_status()
                self.dbg.debug_register()
                self.dbg.debug_fifos()
            machine.idle()

        self.sm.irq(0)

        if self.dbg:
            print("\n=== Transfer Complete ===")
            print("Final state:")
            self.dbg.debug_pio_status()
            self.dbg.debug_register()
            self.dbg.debug_fifos()

    def draw_test_pattern(self, sprite):
        # Get original 32-bit addresses
        palette_addr = addressof(sprite.palette_bytes)
        sprite_addr = addressof(sprite.pixel_bytes)
        fb_addr = self.write_addr

        print(f"\nOriginal 32-bit addresses:")
        print(f"Palette: 0x{palette_addr:08x}")
        print(f"Sprite:  0x{sprite_addr:08x}")
        print(f"FB:      0x{fb_addr:08x}")

        # PIO transfer with original 32-bit addresses
        self.sm.active(0)
        self.sm.restart()

        print("\nStarting PIO transfer...")

        self.sm.put(palette_addr)
        self.sm.put(sprite_addr)
        self.sm.put(fb_addr)  # PIO will handle alignment internally


        print(f"Sent addresses to PIO:")
        print(f"  Palette: 0x{palette_addr:08x}")
        print(f"  Sprite:  0x{sprite_addr:08x}")
        print(f"  FB:      0x{fb_addr:08x}")

        self.sm.active(1)

        # Monitor with timeout
        timeout = 100000
        self.dbg.debug_buffer(self.dbg.debug_bytes)

        while timeout > 0 and not self.finished:
            if timeout % 100 == 0:
                print(f"-- IN LOOP ... ({timeout})")
                self.dbg.debug_register()
                self.dbg.debug_dma(self.dma_out, "SM RX DEBUG", "SM RX DEBUG", 0)
                self.dbg.debug_buffer(self.dbg.debug_bytes)

            timeout -= 1

        if timeout == 0:
            print("ERROR: Transfer timeout!")
        else:
            print("Transfer complete")
