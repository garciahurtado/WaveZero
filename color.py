def color_mix(c1, c2, mix):
    """Returns a 24 bit (true color) bytes array"""
    
    ret = bytearray(b'')
    ret.append( (c1[0] * mix + c2[0] * (255 - mix)) // 255 )
    ret.append( (c1[1] * mix + c2[1] * (255 - mix)) // 255 )
    ret.append( (c1[2] * mix + c2[2] * (255 - mix)) // 255 )
    
    return int(ret.hex(), 24)

def rgb_to_565(rgb):
    """ Convert RGB values to 5-6-5 bit format (16bit) """
    r5 = (rgb[0] >> 3) & 0b11111
    g6 = (rgb[1] >> 2) & 0b111111
    b5 = (rgb[2] >> 3) & 0b11111
    
    # Pack the 5-6-5 bit values into a 16-bit integer
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    return rgb565