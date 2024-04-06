import color_lib

def color_mix(c1, c2, mix):
    """Returns a 24 bit (true color) bytes array"""
    r1, g1, b1 = c1
    r2, g2, b2 = c2
    # h1, s1, l1 = rgb_to_hsl(r1, g1, b1)
    # h2, s2, l2 = rgb_to_hsl(r2, g2, b2)
    # h = h1 + (h2 - h1) * mix
    # s = s1 + (s2 - s1) * mix
    # l = l1 + (l2 - l1) * mix
    # r, g, b = hsl_to_rgb(h, s, l)

    r = r1 + (r2 - r1) * mix
    g = g1 + (g2 - g1) * mix
    b = b1 + (b2 - b1) * mix

    return [r, g, b]

def rgb_to_565(rgb):
    """ Convert RGB values to 5-6-5 bit format (16bit) """
    r5 = (rgb[0] >> 3) & 0b11111
    g6 = (rgb[1] >> 2) & 0b111111
    b5 = (rgb[2] >> 3) & 0b11111
    
    # Pack the 5-6-5 bit values into a 16-bit integer
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    return rgb565

def rgb_to_hex(values):
    total = 0
    for val in reversed(values):
        total = (total << 8) + val
    return total 

def rgb_to_hsl(r, g, b):
    r /= 255
    g /= 255
    b /= 255
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    h, s, l = 0, 0, (max_val + min_val) / 2

    if max_val != min_val:
        d = max_val - min_val
        s = d / (2 - max_val - min_val) if l > 0.5 else d / (max_val + min_val)
        if max_val == r:
            h = (g - b) / d + (6 if g < b else 0)
        elif max_val == g:
            h = (b - r) / d + 2
        else:
            h = (r - g) / d + 4
        h /= 6

    return h, s, l

def hsl_to_rgb(h, s, l):
    if s == 0:
        r = g = b = l
    else:
        def hue_to_rgb(p, q, t):
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1/6:
                return p + (q - p) * 6 * t
            if t < 1/2:
                return q
            if t < 2/3:
                return p + (q - p) * (2/3 - t) * 6
            return p

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)

    return int(r * 255), int(g * 255), int(b * 255)

def make_palette(num_colors, start_color, end_color):
    '''Sets up a color palette by mixing gradually between the two colors. The resulting colors will be saved as RGB565 for efficiency'''
    palette = []
    step = 1/num_colors

    # Add colors to palette
    for i in range(num_colors):
        # Calculate color value
        newcolor = color_mix(start_color, end_color, i*step) 
        palette.append(int(rgb_to_565(newcolor)))

    return palette

def make_color(rgb):
    red = rgb[0] / 255
    green = rgb[1] / 255
    blue = rgb[2] / 255
    color = color_lib.Color()
    color.red = red
    color.green = green
    color.blue = blue
    return color