class SpriteDraw:
    def __init__(self):
        pass

    @staticmethod
    def _dot_tiny(display, x, y, dot_color):
        print(display)
        print(f"-- dot tiny ({dot_color:06x})  --")
        """
        Draw a single dot/pixel for the sprite on the display buffer.

            display: The display buffer object to draw on
            x (int): X coordinate for the dot
            y (int): Y coordinate for the dot
        """
        display.pixel(x, y, dot_color)

    @staticmethod
    def _dot(display, x, y, dot_color):
        print(display)
        print(f"-- dot ({dot_color:06x}) --")
        """
            Draw a 2x2 pixel "dot" in lieu of the sprite image.

            Args:
                display: Display buffer object
                x (int): X coordinate for top-left of the 2x2 dot
                y (int): Y coordinate for top-left of the 2x2 dot
                color (int, optional): RGB color value. Uses sprite's dot_color if None
        """
        display.pixel(x, y, dot_color)
        display.pixel(x + 1, y, dot_color)
        display.pixel(x, y + 1, dot_color)
        display.pixel(x + 1, y + 1, dot_color)