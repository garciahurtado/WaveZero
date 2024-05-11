import asyncio
import framebuf
from anim.animation import Animation
from framebuffer_palette import FramebufferPalette


class PaletteRotate(Animation):
    rotated_palettes: []
    palette: FramebufferPalette
    slice: []

    def __init__(self, palette, interval, slice=[]):
        super().__init__(palette, None)

        self.palette = palette # Must be an object of type Framebuffer / FramebufferPalette

        self.interval_ms = interval
        self.color_idx = 0
        self.current_idx = 0
        self.ellapsed_ms = 0
        self.running = False

        # Build a series of prerotated palettes to swap during runtime
        rotated_palettes = [self.palette.clone()] # The first palette in the list is equal to the original

        if slice:
            self.slice = slice
            num_colors = slice[1] - slice[0]
            assert num_colors >= 1

            for i in range(slice[0], slice[1]):
                new_palette = self.palette.clone()

                for c in range(num_colors+1):
                    # Shift the color by the palette index + the color index
                    old_color = i + c
                    old_color = old_color % (num_colors)
                    old_color = self.palette.get_bytes(old_color)

                    new_palette.set_bytes(c, old_color)

                rotated_palettes.append(new_palette)

            print(f"Added {len(rotated_palettes)} total palettes")

        self.rotated_palettes = rotated_palettes


    async def run_loop(self):
        # if self.slice:
        #     idx_range = self.slice
        # else:
        #     idx_range = [0, len(self.rotate_values)]
        new_bytearray = self.rotated_palettes[self.current_idx].palette

        self.palette.__init__(new_bytearray)

        self.current_idx += 1
        if self.current_idx >= len(self.rotated_palettes):
            self.current_idx = 0

        # Run 5 times per second
        await asyncio.sleep(self.interval_ms/1000/5)