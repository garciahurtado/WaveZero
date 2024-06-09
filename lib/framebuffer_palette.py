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

    def __init__(self, palette):
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

    def _rgb_to_565(self, r, g, b):
        return ((b & 0xf8) << 5) | ((g & 0x1c) << 11) | (r & 0xf8) | ((g & 0xe0) >> 5)

    def rgb_to_565(self, rgb):
        """ Convert RGB values to 5-6-5 bit BGR format (16bit) """
        if self.color_mode == self.BGR565:
            r, g, b = rgb[0], rgb[1], rgb[2]
        else:
            r, g, b = rgb[2], rgb[1], rgb[0]

        res = (r & 0b11111000) << 8
        res = res + ((g & 0b11111100) << 3)
        res = res + (b >> 3)

        return res

    def set_rgb(self, index, color):
        if self.color_mode == self.BGR565:
            color = self.rgb_to_565([color[1], color[1], color[0]])
        else:
            color = self.rgb_to_565([color[0], color[1], color[1]])

        self.pixel(index, 0, color)

    def get_rgb(self, index):
        index += self.index_offset
        index = index % self.num_colors
        color = self.pixel(index, 0)
        color = colors.rgb565_to_rgb(color)
        return color

    def set_bytes(self, index, color):
        # Convert the color value to bytes
        color_bytes = color.to_bytes(2, 'little')

        # Convert the flipped bytes back to an integer
        color = int.from_bytes(color_bytes, 'big')

        # Set the color in the underlying data structure
        self.pixel(index, 0, color)

    def get_bytes(self, index):
        # index += self.index_offset
        # index = index % self.num_colors
        # print(f"{index}")
        color = self.pixel(index, 0)
        color_bytes = color.to_bytes(2, 'big')
        color = int.from_bytes(color_bytes, 'little')
        return color

    def flip_bytes(self, color):
        color_bytes = color.to_bytes(2, 'little')
        color = int.from_bytes(color_bytes, 'big')
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
            color = self.get_bytes(i)
            j = self.num_colors - i - 1
            new_palette.set_bytes(j, color)

        return new_palette

    def pick_from_value(self, value, max, min=0):
        """ Given a value that is part of a range, pick the color index on the palette which represents the same ratio"""
        if value < min:
            value = min
        if value > max:
            value = max

        my_range = max - min
        my_value = value - min

        idx = int((my_value / my_range) * self.num_colors)
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
