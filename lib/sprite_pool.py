from scaled_sprite import ScaledSprite
from sprite_group import SpriteGroup


class SpritePool:
    reserve_sprites: [] = []
    active_sprites: [] = []
    lane_width = 0
    camera = None
    base_sprite = None

    def __init__(self, size=0, camera=None, lane_width=0, base_sprite=None):
        self.lane_width = lane_width
        self.camera = camera

        base_sprite.visible = False
        base_sprite.active = False
        base_sprite.set_camera(self.camera)
        self.base_sprite = base_sprite


        for i in range(size):
            new_sprite = base_sprite.clone()
            new_sprite.visible = False
            new_sprite.active = False
            self.reserve_sprites.append(new_sprite)

    def activate(self, sprite):
        """ Given a Sprite, make it active and visible, reset it, remove it from the available pool,
        and add it to the active pool"""

        sprite.reset()
        sprite.has_physics = True

        if sprite in self.reserve_sprites:
            self.reserve_sprites.remove(sprite)
        #
        # if sprite not in self.active_sprites:
        #     self.active_sprites.append(sprite)

    def add(self, new_sprite):
        """ Add a new sprite to the available pool, in order to recycle it"""
        new_sprite.reset()
        new_sprite.visible = False
        new_sprite.active = False
        new_sprite.has_physics = False
        self.reserve_sprites.append(new_sprite)

    def get_new(self):
        print(f"New sprite from pool [{len(self.reserve_sprites)}]")
        sprite = self.reserve_sprites[0]
        self.activate(sprite)
        return sprite