import framebuf
import color_util as colors

class FramebufferPalette(framebuf.FrameBuffer):
    """
    A color palette in framebuffer format (rgb565), ready to be used by display.blit()
    """
    palette: bytearray
    num_colors: int = 0

    # By introducing an offset, we can "rotate" the colors in the palette without changing the data
    index_offset: int = 0
    RGB565 = 0
    BGR565 = 1
    color_mode = BGR565

    def __init__(self, palette, color_mode=None):
        if color_mode:
            self.color_mode = color_mode

        self.index_offset = 0
        set_colors = []

        if isinstance(palette, int):
            self.num_colors = palette
            palette = bytearray(palette * 2)

            self.palette = palette
        elif isinstance(palette, bytearray):
            self.num_colors = len(palette) // 2
            self.palette = palette
        else:
            """ you can also pass a list of RGB tuples to the constructor"""
            set_colors = palette

            self.num_colors = len(set_colors)
            self.palette = bytearray(self.num_colors * 2) # 2 bytes per color (RGB565)

        super().__init__(self.palette, self.num_colors, 1, framebuf.RGB565)

        for i, color in enumerate(set_colors):
            self.set_rgb(i, color)

    def __len__(self):
        return self.num_colors

    def __add__(self, second_palette):
        """ Override `+` so that we can merge two palettes easily """

        print(f"Adding palettes ... {self.num_colors} + {second_palette.num_colors}")
        total_colors = self.num_colors + second_palette.num_colors
        new_palette = FramebufferPalette(total_colors)

        for i in range(self.num_colors):
            new_palette.set_bytes(i, self.get_bytes(i))

        for j in range(second_palette.num_colors):
            new_palette.set_bytes(j + self.num_colors, second_palette.get_bytes(j))

        return new_palette

    def __getitem__(self, index):
        return self.get_bytes(index)

    def set_rgb(self, index, color):
        if isinstance(color, int):
            pass
        elif self.color_mode == self.BGR565:
            color = colors.rgb_to_565([color[2], color[1], color[0]])
        else:
            color = colors.rgb_to_565([color[0], color[1], color[2]])

        self.pixel(index, 0, color)

    def get_rgb(self, index):
        index += self.index_offset
        index = index % self.num_colors
        color = self.pixel(index, 0)
        color = colors.rgb565_to_rgb(color, self.color_mode)
        return color

    def set_bytes(self, index, color):
        # Convert the color value to bytes
        color_bytes = color.to_bytes(2, 'big')

        # Convert the flipped bytes back to an integer
        color = int.from_bytes(color_bytes, 'big')

        # Set the color in the underlying data structure
        self.pixel(index, 0, color)

    def set_int(self, index, color):
        self.pixel(index, 0, color)

    def get_bytes(self, index, invert=True):
        """ Since the palette already stores colors in original screen format, for efficiency,
        there is no need to convert the color on the way out, presuming its meant for the screen"""
        color = self.pixel(index, 0)

        if invert:
            color_bytes = color.to_bytes(2, 'big')
            color = int.from_bytes(color_bytes, 'little')

        return color

    def clone(self):
        new_palette = FramebufferPalette(bytearray(self.num_colors * 2))
        for i in range(0, self.num_colors):
            color = self.pixel(i, 0)
            new_palette.pixel(i, 0, color)

        return new_palette

    def mirror(self):
        new_palette = FramebufferPalette(self.num_colors)
        for i in range(0, self.num_colors):
            color = self.get_bytes(i, False)
            j = self.num_colors - i - 1
            new_palette.pixel(j, 0, color)

        return new_palette

    def pick_from_value(self, value, max, min=0):
        """ Given a value that is part of a range, pick the color index on the palette which represents the same ratio"""
        if value < min:
            value = min
        if value > max:
            value = max

        my_range = max - min
        my_value = value - min

        idx = round((my_value / my_range) * self.num_colors)
        return idx

    @staticmethod
    def pick_from_palette(palette, value, max=0, min=0):
        """ Static version of the above """
        if value < min:
            value = min
        if value > max:
            value = max

        my_range = max - min
        my_value = value - min

        idx = int((my_value / (my_range * 1.0)) * (palette.num_colors - 1))
        if idx < 0:
            idx = 0

        return idx
