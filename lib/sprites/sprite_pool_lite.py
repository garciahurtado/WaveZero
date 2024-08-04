import utime
from uarray import array
from sprites.sprite_types import create_sprite

class SpritePool:
    pool = []

    def __init__(self, pool_size):
        self.pool_size = pool_size
        self.sprites = [create_sprite() for _ in range(pool_size)]
        self.free_indices = array('H', range(pool_size))  # Unsigned short array for indices
        self.free_count = pool_size
        self.active_indices = array('H', [0] * pool_size)
        self.active_count = 0

    def create(self):
        new_sprite = create_sprite()
        self.pool.append(new_sprite)
        return new_sprite


    def get(self, sprite_type):
        """Get the first sprite available from the pool and return it"""
        if self.free_count == 0:
            raise RuntimeError("Sprite pool is empty. Consider increasing pool size.")

        self.free_count -= 1
        index = self.free_indices[self.free_count]
        sprite = self.sprites[index]

        sprite.sprite_type = sprite_type
        sprite.current_frame = 0
        sprite.born_ms = utime.ticks_ms() # reset creation timestamp

        sprite.active = True
        sprite.visible = True

        self.active_indices[self.active_count] = index
        self.active_count += 1

        return sprite, index

    def release(self, sprite):
        if sprite.active:
            sprite.active = False
            sprite.visible = False

            # Find and remove the sprite from active_indices
            for i in range(self.active_count):
                if self.sprites[self.active_indices[i]] is sprite:
                    self.active_count -= 1
                    self.active_indices[i] = self.active_indices[self.active_count]
                    break

            # Add the index back to free_indices
            self.free_indices[self.free_count] = self.sprites.index(sprite)
            self.free_count += 1

    @property
    def active_sprites(self):
        """Return a generator of active sprites"""
        return (self.sprites[i] for i in self.active_indices[:self.active_count])

    def __len__(self):
        """Return the number of active sprites"""
        return self.active_count