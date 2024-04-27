from sprite import Sprite


class ScaledSprite(Sprite):
    frames = []
    current_frame = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.width and self.height:
            self.ratio = self.width / self.height

        if self.frames:
            self.set_frame(0)

    def set_frame(self, index):
        self.current_frame = index
        self.pixels = self.frames[index]