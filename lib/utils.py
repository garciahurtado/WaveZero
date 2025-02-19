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
