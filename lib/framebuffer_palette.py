import framebuf
import color_util as colors

class FramebufferPalette(framebuf.FrameBuffer):
    """
    A color palette in framebuffer format (rgb565), ready to be used by display.blit()
    """
    palette: bytearray
    num_colors = 0

    def __init__(self, palette):

        set_colors = []

        if isinstance(palette, int):
            self.num_colors = palette
            palette = bytearray(palette * 2)

            self.palette = palette
        elif isinstance(palette, bytearray):
            self.num_colors = int(len(palette) / 2)
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
        return len(self.palette)

    def __add__(self, second_palette):
        print(f"Adding palettes ... {self.num_colors} + {second_palette.num_colors}")
        total_colors = self.num_colors + second_palette.num_colors
        new_palette = FramebufferPalette(bytearray(total_colors * 2))

        for i in range(self.num_colors):
            new_palette.set_bytes(i, self.get_bytes(i))

        for j in range(second_palette.num_colors):
            new_palette.set_bytes(j + self.num_colors, second_palette.get_bytes(j))

        return new_palette

    def set_rgb(self, index, color):
        color = colors.rgb_to_565([color[0], color[1], color[2]])  # returns 2 bytes
        self.pixel(index, 0, color)

    def get_rgb(self, index):
        color = self.pixel(index, 0)
        color = colors.rgb565_to_rgb(color)
        return color

    def set_bytes(self, index, color):
        # print(color)
        # color = int.from_bytes(bytearray([color]), "little")
        # # color = color.to_bytes(2, 'big')
        # print(color)
        self.pixel(index, 0, int(color))

    def get_bytes(self, index):
        color = self.pixel(index, 0)
        return color

    def clone(self):
        new_palette = FramebufferPalette(bytearray(self.num_colors * 2))
        for i in range(0, self.num_colors):
            color = self.pixel(i, 0)
            new_palette.pixel(i, 0, color)

        return new_palette

    def mirror(self):
        new_palette = FramebufferPalette(bytearray(self.num_colors * 2))
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

