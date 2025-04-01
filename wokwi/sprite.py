from uarray import array
import struct

def to_bytes(num):
    # Break down the 16-byte number into individual byte representations
    byte_representations = []
    for i in range(16):
        # Shift and mask to get each byte, from most to least significant
        byte = hex((num >> (8 * (15 - i))) & 0xFF)
        byte_representations.append(byte)

    return tuple(byte_representations)


def get_sprite_bytes():
    sprite_hex = [
        bytearray.fromhex('0102030203020101'),  # 8 bytes
        bytearray.fromhex('1010203020101000')  # 8 bytes
    ]

    # Combine both rows into one array
    sprite_bytes = array('B')
    sprite_bytes.extend(sprite_hex[0])  # First 8 bytes
    sprite_bytes.extend(sprite_hex[1])  # Next 8 bytes

    return sprite_bytes  # Total 16 bytes exactly


def generate_diagonal_stripes():
    # Create a 16x16 grid of 4-bit color indices (0-4)
    sprite_grid = []
    for y in range(16):
        row = []
        for x in range(16):
            # Diagonal stripes: (x - y) determines the color band
            band = (x - y) // 2  # Adjust thickness with division
            color = (band % 4) + 1  # Cycles through 1, 2, 3, 4
            row.append(color)
        sprite_grid.append(row)

    # Pack two 4-bit pixels into each byte
    sprite_bytes = array('B')
    for y in range(16):
        for x in range(0, 16, 2):  # Process 2 pixels at a time
            pixel1 = sprite_grid[y][x]
            pixel2 = sprite_grid[y][x + 1]
            packed_byte = (pixel1 << 4) | pixel2
            sprite_bytes.append(packed_byte)

    return sprite_bytes

