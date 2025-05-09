# import functools # Not available in MP
# import warnings # Not available in MP
# from typing import TypeVar ParamSpec, Callable

import math
import colors


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
    print(repr(obj))

def pprint_pure(data, indent=0):
    """
    Prints nested dictionaries, lists, and tuples with indentation using
    basic Python features. Simulates basic pprint functionality.

    Args:
        data: The data structure to print.
        indent (int): Current indentation level (spaces).
    """
    indent_space = ' ' * indent

    # Handle Dictionaries
    if isinstance(data, dict):
        if not data:
            print("{}")
            return

        print("{")
        items = list(data.items()) # Get items to safely check length later
        for i, (key, value) in enumerate(items):
            print(f"{indent_space}  {repr(key)}: ", end="") # Print key (repr adds quotes to strings)
            pprint_pure(value, indent + 2) # Recursively print value
            # Add comma and newline unless it's the last item
            print("," if i < len(items) - 1 else "")
        print(f"{indent_space}}}")

    # Handle Lists and Tuples
    elif isinstance(data, (list, tuple)):
        is_tuple = isinstance(data, tuple)
        open_bracket, close_bracket = ('(', ')') if is_tuple else ('[', ']')

        if not data:
            print(f"{open_bracket}{close_bracket}")
            return

        print(f"{open_bracket}")
        for i, item in enumerate(data):
            print(f"{indent_space}  ", end="") # Indent item line
            pprint_pure(item, indent + 2) # Recursively print item
            # Add comma and newline unless it's the last item
            print("," if i < len(data) - 1 else "")
        print(f"{indent_space}{close_bracket}")

    # Handle other simple types
    else:
        print(repr(data), end="") # Use repr for consistent representation

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


# rT = TypeVar('rT') # return type
# pT = ParamSpec('pT') # parameters type
def deprecated(func: Callable[pT, rT]) -> Callable[pT, rT]:
    """ This isn't going to work until we figure out how to bring functools into micropython """
    """Use this decorator to mark functions as deprecated.
    Every time the decorated function runs, it will emit
    a "deprecation" warning."""
    @functools.wraps(func)
    def new_func(*args: pT.args, **kwargs: pT.kwargs):
        warnings.simplefilter('always', DeprecationWarning)  # turn off filter
        warnings.warn(f"Call to a deprecated function {func.__name__}.",
                      category=DeprecationWarning,
                      stacklevel=2)
        warnings.simplefilter('default', DeprecationWarning)  # reset filter
        return func(*args, **kwargs)
    return new_func