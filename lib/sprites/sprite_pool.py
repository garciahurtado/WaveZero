from uarray import array

from sprites.sprite import Sprite


class SpritePool:
    reserve_sprites: [] = []
    active_sprites: [] = []
    camera = None
    base_sprite = None

    def __init__(self, size=0, camera=None, base_sprite=None, active_sprites=None):
        self.camera = camera
        self.reserve_sprites = []
        self.active_sprites = active_sprites

        base_sprite.visible = False
        base_sprite.active = False
        base_sprite.set_camera(self.camera)
        self.base_sprite = base_sprite

        for i in range(size):
            new_sprite = base_sprite.clone()
            self.add(new_sprite)

    def __len__(self):
        return len(self.active_sprites)

    def __iter__(self):
        return iter(self.active_sprites)


    def add(self, new_sprite):
        """ Add a new sprite to the available pool, in order to recycle it"""
        new_sprite.visible = False
        new_sprite.active = False
        new_sprite.has_physics = False
        new_sprite.pool = self
        self.reserve_sprites.append(new_sprite)

    def get_new(self):
        if len(self.reserve_sprites) < 1:
            print("ERROR: NO SPRITES LEFT IN POOL!!!")
            return False

        sprite = self.reserve_sprites[0] # FIFO
        self.activate(sprite)

        return sprite

    def activate(self, sprite):
        """ Given a Sprite, make it active and visible, reset it, remove it from the available pool,
        and add it to the active pool"""
        sprite.has_physics = True

        if sprite in self.reserve_sprites:
            self.reserve_sprites.remove(sprite)

        if sprite.pos_type == Sprite.POS_TYPE_FAR:
            self.active_sprites.insert(0, sprite)
        else:
            self.active_sprites.append(sprite)

        sprite.reset()
        return sprite

    def update(self, elapsed):
        for sprite in self.active_sprites:
            if not sprite.active:
                sprite.kill()
                self.active_sprites.remove(sprite)
                self.add(sprite)

            sprite.update(elapsed)
            sprite.update_frame()


    def show(self, display):
        for my_sprite in self.active_sprites:
            my_sprite.show(display)

