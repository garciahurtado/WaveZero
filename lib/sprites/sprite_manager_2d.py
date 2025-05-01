from framebuf import FrameBuffer

from images.image_loader import ImageLoader
from profiler import Profiler
from scaler.const import DEBUG_PHYSICS
from sprites.sprite_manager import SpriteManager
from sprites.sprite_types import SpriteType as types, FLAG_PHYSICS, FLAG_ACTIVE, FLAG_VISIBLE

prof = Profiler()

class SpriteManager2D(SpriteManager):
    """ Specialized version of SpriteManager that doesnt need to do any 3D projections (although the parent-child
    hierarchy should probably be the other way around)
    """
    last_update_ms = 0

    def update_sprite(self, sprite, meta, elapsed):
        """ Updates a single sprite over an 'elapsed' time, by updating the x and y draw coordinates of the sprite based
        on its speed (or any other physics or time based effects). Returns True if it updated a sprite, False otherwise.
        It only works with thin / 2D sprites (ie: structs)
        """

        active = types.get_flag(sprite, types.FLAG_ACTIVE)
        if not active:
            print(f"Returning due to active:{active}")
            return False

        old_speed = sprite.speed

        if types.get_flag(sprite, FLAG_PHYSICS) == True:
            self.phy.apply_speed(sprite, elapsed)

        sprite.speed = old_speed

        scaled_width = meta.width * sprite.scale
        scaled_height = meta.height * sprite.scale

        draw_x, draw_y = self.phy.get_draw_pos(sprite, scaled_width, scaled_height)
        x, y = self.phy.get_pos(sprite)

        if DEBUG_PHYSICS:
            dir_x, dir_y = self.phy.get_dir(sprite)
            print(f"SPRITE 2D UPDATE :")
            print(f"  Pos:      {x},{y}")
            print(f"  Draw:     {draw_x},{draw_y}")
            print(f"  Dir:      {dir_x},{dir_y}")
            print(f"  Speed:    {sprite.speed}")
            print(f"  Elaps.    {elapsed}")

        return True

    def load_sprite_image(self, meta, sprite_type):
        """ Overrides parent to get rid of preloaded scaled sprite frames from v1. Eventually should be refactored back
         into SpriteManagerBase"""
        orig_img = ImageLoader.load_image(meta.image_path, meta.width, meta.height)
        if isinstance(orig_img, list):
            orig_img = orig_img[0]

        self.sprite_palettes[sprite_type] = orig_img.palette
        meta.palette = orig_img.palette
        self.set_alpha_color(meta)
        img_list = [orig_img] # Legacy
        return img_list

    def show(self, display: FrameBuffer):
        sprite_type = self.sprite_metadata['none']
        for sprite in self.pool.sprites:
            visible = types.get_flag(sprite, FLAG_VISIBLE)

            if visible:
                h_scale = v_scale = sprite.scale
                self.scaler.draw_sprite(
                    sprite_type, sprite, self.image,
                    h_scale=h_scale, v_scale=v_scale)

    def spawn(self, sprite_type):
        new_inst, idx = self.pool.get(sprite_type)
        self.phy.set_pos(new_inst, 50, 24)

        return new_inst, idx




