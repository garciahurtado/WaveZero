import uarray as array
import gc

class SpriteList:
    def __init__(self, max_sprites=100):
        self.max_sprites = max_sprites
        self.sprites = [None] * max_sprites
        self.count = 0
        self.first_empty = 0

    def add(self, sprite):
        if self.count >= self.max_sprites:
            return False

        index = self.first_empty
        while self.sprites[index] is not None:
            index = (index + 1) % self.max_sprites

        self.sprites[index] = sprite
        self.count += 1
        self.first_empty = (index + 1) % self.max_sprites
        return True

    def remove(self, sprite):
        for i in range(self.max_sprites):
            if self.sprites[i] is sprite:
                self.sprites[i] = None
                self.count -= 1
                self.first_empty = min(self.first_empty, i)
                return True
        return False

    def __iter__(self):
        for sprite in self.sprites:
            if sprite is not None:
                yield sprite

    def __len__(self):
        return self.count