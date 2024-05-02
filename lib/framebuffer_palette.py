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

        if isinstance(palette, bytearray):
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
        new_palette = FramebufferPalette(bytearray(self.palette + second_palette.palette))
        return new_palette

    def set_rgb(self, index, color):
        color = colors.rgb_to_565([color[0], color[1], color[2]])  # returns 2 bytes
        self.pixel(index, 0, color)

    def get_rgb(self, index):
        color = self.pixel(index, 0)
        color = colors.rgb565_to_rgb(color)
        return color

    def set_bytes(self, index, color):
        self.pixel(index, 0, color)

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
