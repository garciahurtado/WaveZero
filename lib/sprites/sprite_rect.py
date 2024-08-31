from sprites.sprite import Sprite

class SpriteRect(Sprite):
    """A Sprite that does not load a bitmap from disk, but serves as an empty canvas for eg. drawing solid backgrounds
    or pixel effects """

    def __init__(self, width, height, filename=None, x=0, y=0, color=0x000000):
        super().__init__(filename, x, y)

        self.width = width
        self.height = height
        self.color = color

    def show(self, display):
        # print(f"SPRITE RECT AT {self.x}, {self.y} ({self.width}, {self.height} - {self.color})")
        if not self.visible:
            return

        display.fill_rect(self.x, self.y, self.width, self.height, self.color)
