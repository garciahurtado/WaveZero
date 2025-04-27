from images.image_loader import ImageLoader
from profiler import Profiler
from scaler.const import DEBUG_PHYSICS
from sprites.sprite_manager import SpriteManager
from sprites.sprite_types import SpriteType as types, FLAG_PHYSICS, FLAG_ACTIVE

prof = Profiler()

class SpriteManager2D(SpriteManager):
    """ Specialized version of SpriteManager that doesnt need to do any 3D projections (although the parent-child
    hierarchy should probably be the other way around)
    """
    last_update_ms = 0

    def update(self, elapsed):
        """ The order here is very important """
        if not elapsed:
            return

        kinds = self.sprite_metadata
        current = self.pool.head
        while current:

            sprite = current.sprite
            kind = kinds[sprite.sprite_type]

            self.update_sprite(sprite, kind, elapsed)

            if not types.get_flag(sprite, FLAG_ACTIVE):
                self.pool.release(sprite, kind)

            current = current.next



    def update_sprite(self, sprite, meta, elapsed):
        """The update function only applies to a single sprite at a time, and it is responsible for
         updating the x and y draw coordinates of the sprite based on its speed.
         Returns True if it updated a sprite, False otherwise
        """

        active = types.get_flag(sprite, types.FLAG_ACTIVE)
        if not active:
            print(f"Returning due to active:{active}")
            return False


        old_speed = sprite.speed
        # sprite.speed = sprite.speed * sprite.scale

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

    def load_img_and_scale(self, meta, sprite_type):
        """ Overrides parent to get rid of preloaded scaled sprite frames from v1 """
        orig_img = ImageLoader.load_image(meta.image_path, meta.width, meta.height)
        if isinstance(orig_img, list):
            orig_img = orig_img[0]

        self.sprite_palettes[sprite_type] = orig_img.palette
        meta.palette = orig_img.palette
        self.set_alpha_color(meta)
        img_list = [orig_img] # Legacy
        return img_list



