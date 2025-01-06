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

def pformat(obj, indent=1, width=80, depth=None):
    return repr(obj)

def pprint(obj, stream=None, indent=1, width=80, depth=None):
    print(repr(obj), file=stream)
