from framebuffer_palette import FramebufferPalette

FLOAT_ERROR = 0.0000005
RGB565 = 1
BGR565 = 2

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


def _rgb_to_565(rgb):
    """ Convert RGB values to 5-6-5 bit BGR format (16bit) """
    r5 = (rgb[2] >> 3) & 0b11111
    g6 = (rgb[1] >> 2) & 0b111111
    b5 = (rgb[0] >> 3) & 0b11111

    # Pack the 5-6-5 bit values into a 16-bit integer
    rgb565 = (r5 << 11) | (g6 << 5) | b5
    return rgb565

def rgb_to_565(rgb,  format=RGB565):
    """ Convert RGB values to 5-6-5 bit BGR format (16bit) """
    if format == RGB565:
        r, g, b = rgb[0], rgb[1], rgb[2]
    else:
        r, g, b = rgb[2], rgb[1], rgb[0]

    res = (r & 0b11111000) << 8
    res = res + ((g & 0b11111100) << 3)
    res = res + (b >> 3)

    return res

def rgb565_to_rgb(rgb565, format=RGB565):

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

    if format and format == RGB565:
        return r, g, b
    else:
        return b, g, r


def rgb_to_hex(rgb):
    """
    Convert RGB values to web hexadecimal color code
    """
    # Ensure RGB values are integers between 0 and 255
    rgb = [int(max(0, min(255, val))) for val in rgb]

    # Convert RGB values to hexadecimal
    # hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)

    hex_color = (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]

    return hex_color


def hex_to_rgb(hex_value):
    # Extract the red, green, and blue components
    red = (hex_value >> 16) & 0xFF
    green = (hex_value >> 8) & 0xFF
    blue = hex_value & 0xFF

    return (red, green, blue)

def hex_to_565(hex_value, format=None):
    # Extract the red, green, and blue components
    red = (hex_value >> 16) & 0xFF
    green = (hex_value >> 8) & 0xFF
    blue = hex_value & 0xFF

    return rgb_to_565((red, green, blue), format=format)


def rgb_to_hsl(rgb):
    """Convert RGB representation towards HSL

    :param r: Red amount (float between 0 and 1)
    :param g: Green amount (float between 0 and 1)
    :param b: Blue amount (float between 0 and 1)
    :rtype: 3-uple for HSL values in float between 0 and 1

    This algorithm came from:
    http://www.easyrgb.com/index.php?X=MATH&H=19#text19

    Here are some quick notion of RGB to HSL conversion:

    >> from colour import rgb2hsl

    Note that if red amount is equal to green and blue, then you
    should have a gray value (from black to white).


    >> rgb2hsl((1.0, 1.0, 1.0))  # doctest: +ELLIPSIS
    (..., 0.0, 1.0)
    >> rgb2hsl((0.5, 0.5, 0.5))  # doctest: +ELLIPSIS
    (..., 0.0, 0.5)
    >> rgb2hsl((0.0, 0.0, 0.0))  # doctest: +ELLIPSIS
    (..., 0.0, 0.0)

    If only one color is different from the others, it defines the
    direct Hue:

    >> rgb2hsl((0.5, 0.5, 1.0))  # doctest: +ELLIPSIS
    (0.66..., 1.0, 0.75)
    >> rgb2hsl((0.2, 0.1, 0.1))  # doctest: +ELLIPSIS
    (0.0, 0.33..., 0.15...)

    Having only one value set, you can check that:

    >> rgb2hsl((1.0, 0.0, 0.0))
    (0.0, 1.0, 0.5)
    >> rgb2hsl((0.0, 1.0, 0.0))  # doctest: +ELLIPSIS
    (0.33..., 1.0, 0.5)
    >> rgb2hsl((0.0, 0.0, 1.0))  # doctest: +ELLIPSIS
    (0.66..., 1.0, 0.5)

    Regression check upon very close values in every component of
    red, green and blue:

    >> rgb2hsl((0.9999999999999999, 1.0, 0.9999999999999994))
    (0.0, 0.0, 0.999...)

    Of course:

    >> rgb2hsl((0.0, 2.0, 0.5))  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    ValueError: Green must be between 0 and 1. You provided 2.0.

    And:
    >> rgb2hsl((0.0, 0.0, 1.5))  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    ValueError: Blue must be between 0 and 1. You provided 1.5.

    """
    r, g, b = [float(v/255) for v in rgb]

    for name, v in {'Red': r, 'Green': g, 'Blue': b}.items():
        if not (0 - FLOAT_ERROR <= v <= 1 + FLOAT_ERROR):
            raise ValueError("%s must be between 0 and 1. You provided %r."
                             % (name, v))

    vmin = min(r, g, b)  ## Min. value of RGB
    vmax = max(r, g, b)  ## Max. value of RGB
    diff = vmax - vmin  ## Delta RGB value

    vsum = vmin + vmax

    l = vsum / 2

    if diff < FLOAT_ERROR:  ## This is a gray, no chroma...
        return (0.0, 0.0, l)

    ##
    ## Chromatic data...
    ##

    ## Saturation
    if l < 0.5:
        s = diff / vsum
    else:
        s = diff / (2.0 - vsum)

    dr = (((vmax - r) / 6) + (diff / 2)) / diff
    dg = (((vmax - g) / 6) + (diff / 2)) / diff
    db = (((vmax - b) / 6) + (diff / 2)) / diff

    if r == vmax:
        h = db - dg
    elif g == vmax:
        h = (1.0 / 3) + dr - db
    elif b == vmax:
        h = (2.0 / 3) + dg - dr

    if h < 0: h += 1
    if h > 1: h -= 1

    return (h, s, l)


def hsl_to_rgb(hsl):
    h, s, l = hsl
    if s == 0:
        r = g = b = l
    else:
        def hue_to_rgb(p, q, t):
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1 / 6:
                return p + (q - p) * 6 * t
            if t < 1 / 2:
                return q
            if t < 2 / 3:
                return p + (q - p) * (2 / 3 - t) * 6
            return p

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue_to_rgb(p, q, h + 1 / 3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1 / 3)

    return int(r * 255), int(g * 255), int(b * 255)


def int_to_bytes(color):
    """Convert a color represented as a 3 byte int, into a bytearray"""
    return bytearray([(color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF])


def bytearray_to_int(bytes_array):
    if len(bytes_array) != 2:
        raise ValueError("Bytearray must have exactly 2 bytes")

    return (bytes_array[1] << 8) | bytes_array[0]

def byte3_to_byte2(rgb_bytes_array):
    if len(rgb_bytes_array) % 3 != 0:
        raise ValueError("Input bytearray length must be a multiple of 3")

    byte2 = bytearray(len(rgb_bytes_array) // 3 * 2)

    for i in range(0, len(rgb_bytes_array), 3):
        r = rgb_bytes_array[i]
        g = rgb_bytes_array[i + 1]
        b = rgb_bytes_array[i + 2]

        # Convert RGB888 to RGB565
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        # rgb565 = ((b & 0xf8) << 5) | ((g & 0x1c) << 11) | (r & 0xf8) | ((g & 0xe0) >> 5)

        # Pack RGB565 into two bytes
        byte2[i // 3 * 2] = rgb565 >> 8
        byte2[i // 3 * 2 + 1] = rgb565 & 0xFF

    return byte2

def make_gradient(start_color: list[int], end_color: list[int], num_colors):
    '''Sets up a color palette by mixing gradually between the two colors. The resulting colors will be saved as RGB565 for efficiency'''
    # palette = FramebufferPalette(bytearray(num_colors*2))
    palette = []

    # Add colors to palette
    for i, hsl in enumerate(color_scale(
            rgb_to_hsl(start_color), rgb_to_hsl(end_color), num_colors - 1)):
        newcolor = hsl_to_rgb(hsl)
        hex = rgb_to_hex(newcolor)
        print(f"{hex:06x}")
        palette.append(hex)
    print()
    return palette



def color_scale(begin_hsl, end_hsl, nb):
    """Returns a list of nb color HSL tuples between begin_hsl and end_hsl

    >> from colour import color_scale

    >> [rgb2hex(hsl2rgb(hsl)) for hsl in color_scale((0, 1, 0.5),
    ...                                               (1, 1, 0.5), 3)]
    ['#f00', '#0f0', '#00f', '#f00']

    >> [rgb2hex(hsl2rgb(hsl))
    ...  for hsl in color_scale((0, 0, 0),
    ...                         (0, 0, 1),
    ...                         15)]  # doctest: +ELLIPSIS
    ['#000', '#111', '#222', ..., '#ccc', '#ddd', '#eee', '#fff']

    Of course, asking for negative values is not supported:

    >> color_scale((0, 1, 0.5), (1, 1, 0.5), -2)
    Traceback (most recent call last):
    ...
    ValueError: Unsupported negative number of colors (nb=-2).

    """

    if nb < 0:
        raise ValueError(
            "Unsupported negative number of colors (nb=%r)." % nb)

    step = tuple([float(end_hsl[i] - begin_hsl[i]) / nb for i in range(0, 3)]) \
        if nb > 0 else (0, 0, 0)

    list = []
    for r in range(0, nb + 1):
        list.append(add_v(begin_hsl, mul(step, r)))

    return list

def mul(step, value):
    return tuple([v * value for v in step])

def add_v(step, step2):
    return tuple([v + step2[i] for i, v in enumerate(step)])

