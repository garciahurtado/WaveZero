import color_lib
from ssd1331_16bit import SSD1331

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
    """ Convert RGB values to 5-6-5 bit BGR format (16bit) """
    r5 = (rgb[2] >> 3) & 0b11111
    g6 = (rgb[1] >> 2) & 0b111111
    b5 = (rgb[0] >> 3) & 0b11111
    
    # Pack the 5-6-5 bit values into a 16-bit integer
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    return rgb565

def rgb565_to_rgb(rgb565):
    """
    Convert a 16-bit color in 5-6-5 bit format to RGB values
    """
    # Extract the 5-bit red value
    r5 = (rgb565 >> 11) & 0b11111
    # Extract the 6-bit green value
    g6 = (rgb565 >> 5) & 0b111111
    # Extract the 5-bit blue value
    b5 = rgb565 & 0b11111

    # Convert 5-bit and 6-bit values back to 8-bit RGB values
    r = (r5 << 3) | (r5 >> 2)
    g = (g6 << 2) | (g6 >> 4)
    b = (b5 << 3) | (b5 >> 2)

    return r, g, b

def rgb_to_hex(rgb):
    """
    Convert RGB values to web hexadecimal color code
    """
    # Ensure RGB values are integers between 0 and 255
    rgb = [int(max(0, min(255, val))) for val in rgb]

    # Convert RGB values to hexadecimal
    hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)

    return hex_color


def rgb_to_hsl(color):
    return color_lib.rgb2hsl((color[0]/255, color[1]/255, color[2]/255))



    r, g, b = color
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

def hsl_to_rgb(hsl):
    h,s,l = hsl
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

def make_palette(start_color:list[int], end_color:list[int], num_colors):
    '''Sets up a color palette by mixing gradually between the two colors. The resulting colors will be saved as RGB565 for efficiency'''
    palette = []
    step = 1/num_colors

    # Add colors to palette
    for hsl in color_scale(
        rgb_to_hsl(start_color), rgb_to_hsl(end_color), num_colors - 1):
        newcolor = hsl_to_rgb(hsl)
        
        newcolor = SSD1331.rgb(newcolor[0], newcolor[1], newcolor[2],)
        palette.append(newcolor)


    return palette

def color_scale(begin_hsl, end_hsl, nb):
    """Returns a list of nb color HSL tuples between begin_hsl and end_hsl

    >>> from colour import color_scale

    >>> [rgb2hex(hsl2rgb(hsl)) for hsl in color_scale((0, 1, 0.5),
    ...                                               (1, 1, 0.5), 3)]
    ['#f00', '#0f0', '#00f', '#f00']

    >>> [rgb2hex(hsl2rgb(hsl))
    ...  for hsl in color_scale((0, 0, 0),
    ...                         (0, 0, 1),
    ...                         15)]  # doctest: +ELLIPSIS
    ['#000', '#111', '#222', ..., '#ccc', '#ddd', '#eee', '#fff']

    Of course, asking for negative values is not supported:

    >>> color_scale((0, 1, 0.5), (1, 1, 0.5), -2)
    Traceback (most recent call last):
    ...
    ValueError: Unsupported negative number of colors (nb=-2).

    """

    if nb < 0:
        raise ValueError(
            "Unsupported negative number of colors (nb=%r)." % nb)

    step = tuple([float(end_hsl[i] - begin_hsl[i]) / nb for i in range(0, 3)]) \
           if nb > 0 else (0, 0, 0)

    def mul(step, value):
        return tuple([v * value for v in step])

    def add_v(step, step2):
        return tuple([v + step2[i] for i, v in enumerate(step)])

    return [add_v(begin_hsl, mul(step, r)) for r in range(0, nb + 1)]