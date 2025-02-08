from profiler import Profiler
from sprites2.sprite_manager import SpriteManager
from sprites2.sprite_types import SpriteType as types, SpriteType, FLAG_PHYSICS, FLAG_ACTIVE
from utils import is_point_within_bounds
import utime

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
            prof.start_profile('mgr.update_one_sprite()')
            sprite = current.sprite
            kind = kinds[sprite.sprite_id]

            self.update_sprite(sprite, kind, elapsed)

            if not types.get_flag(sprite, FLAG_ACTIVE):
                self.pool.release(sprite, kind)

            current = current.next
            prof.end_profile('mgr.update_one_sprite()')


    def update_sprite(self, sprite, meta, elapsed):
        """The update function only applies to a single sprite at a time, and it is responsible for
         updating the x and y draw coordinates of the sprite based on its speed.
         Returns True if it updated a sprite, False otherwise
        """

        active = types.get_flag(sprite, types.FLAG_ACTIVE)
        if not active:
            print(f"Returning due to active:{active}")
            return False

        prof.start_profile('mgr.update_sprite.physics')
        if SpriteType.get_flag(sprite, FLAG_PHYSICS) == True:
            self.phy.apply_speed(sprite, elapsed)
        prof.end_profile('mgr.update_sprite.physics')

        scaled_width = meta.width * sprite.scale
        scaled_height = meta.height * sprite.scale

        sprite.draw_x, sprite.draw_y = self.phy.get_draw_pos(sprite, scaled_width, scaled_height, True)

        if self.debug_inst:
            print("2D UPDATE SPRITE:")
            print(f"  Dir {dir}")
            print(f"  Speed {sprite.speed}")
            print(f"  Elapsed {elapsed}")
            print(f"  FORMULA: new_y += sprite.speed * dir_y * elapsed")

        return True

    def is_within_bounds(self, coords):
        x, y = coords
        return is_point_within_bounds([x, y], self.bounds)


