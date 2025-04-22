import math

def aligned_buffer(size, alignment=4):
    """ Create a buffer of 'size' bytes aligned to a memory address power of 'alignment'"""

    # Create a buffer slightly larger than needed
    buf = bytearray(size + alignment - 1)

    # Calculate the aligned address
    addr = id(buf)
    aligned_addr = (addr + alignment - 1) & ~(alignment - 1)

    # Create a memoryview of the aligned portion
    offset = aligned_addr - addr
    aligned_buf = memoryview(buf)[offset:offset + size]

    return aligned_buf

def dist_between(from_x, from_y, to_x, to_y):
    dx = to_x - from_x
    dy = to_y - from_y
    if not dx and not dy:
        return 0

    return math.sqrt(dx**2 + dy**2)


def pformat(obj, indent=1, width=80, depth=None):
    return repr(obj)

def pprint(obj, stream=None, indent=1, width=80, depth=None):
    print(repr(obj), file=stream)


""" These two methods originally in sprite_scaler.py """
def draw_dot(self, x, y, type):
    self.draw_x = x
    self.draw_y = y
    self.alpha = type.alpha_color

    color = type.dot_color
    color = colors.hex_to_565(color)

    self.framebuf.scratch_buffer = self.framebuf.scratch_buffer_4
    self.framebuf.frame_width = self.frame_height = 4
    display = self.framebuf.scratch_buffer

    display.pixel(0, 0, color)
    self.finish_sprite()

def draw_fat_dot(self, x, y, type):
        """
            Draw a 2x2 pixel "dot" in lieu of the sprite image.

            Args:
                display: Display buffer object
                x (int): X coordinate for top-left of the 2x2 dot
                y (int): Y coordinate for top-left of the 2x2 dot
                color (int, optional): RGB color value. Uses sprite's dot_color if None
        """
        self.draw_x = x
        self.draw_y = y
        self.alpha = type.alpha_color

        color = type.dot_color
        color = colors.hex_to_565(color)

        self.framebuf.scratch_buffer = self.framebuf.scratch_buffer_4
        self.framebuf.frame_width = self.frame_height = 4
        display = self.framebuf.scratch_buffer

        display.pixel(0, 0, color)
        display.pixel(0 + 1, 0, color)
        display.pixel(0, 0 + 1, color)
        display.pixel(0 + 1, 0 + 1, color)
        self.finish_sprite()