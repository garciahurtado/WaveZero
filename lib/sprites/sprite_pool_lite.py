from sprites.sprite_types import SpriteData, SpriteMetadata

class SpritePool:
    def __init__(self, pool_size, sprite_types):
        self.pool_size = pool_size
        self.sprite_types = sprite_types
        self.pool = [LightSprite() for _ in range(pool_size)]
        self.active_sprites = []  # New array to store active sprites
        self.sprite_images = {}  # Flyweight store for shared image data

    def create(self, sprite_type, x, y, z, speed):
        if len(self.active_sprites) >= self.pool_size:
            return None  # Pool is full

        for sprite in self.pool:
            if not sprite.active:
                sprite.active = True
                sprite.x = x
                sprite.y = y
                sprite.z = z
                sprite.speed = speed
                sprite.type = sprite_type
                sprite.frame = 0
                self.active_sprites.append(sprite)
                return sprite

        return None  # This should never happen if active_count is correct

    def release(self, sprite):
        if sprite.active:
            sprite.active = False
            self.active_sprites.remove(sprite)

    def update(self, sprite, elapsed):
        if not sprite.active:
            return False

        sprite.z += sprite.speed * elapsed

        if sprite.z > 4000 or sprite.z < -40:  # Using constants from Sprite3D
            self.release(sprite)
            return False

        sprite.frame = self.get_frame_idx(sprite)
        return True

    def get_frame_idx(self, sprite):
        # Simplified frame index calculation
        # In a real implementation, this would depend on the sprite's z position
        return (sprite.frame + 1) % len(self.sprite_images[sprite.type])

    def load_sprite_images(self, sprite_type, images):
        self.sprite_images[sprite_type] = images