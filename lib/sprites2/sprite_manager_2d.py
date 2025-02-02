from profiler import Profiler
from sprites2.sprite_manager import SpriteManager
from sprites2.sprite_types import SpriteType as types, SpriteType, FLAG_PHYSICS
from utils import is_point_within_bounds

prof = Profiler()

class SpriteManager2D(SpriteManager):
    """ Specialized version of SpriteManager that doesnt need to do any 3D projections (although the parent-child
    hierarchy should probably be the other way around)
    """

    def update_sprite(self, sprite, meta, elapsed):
        """The update function only applies to a single sprite at a time, and it is responsible for
         updating the x and y draw coordinates of the sprite based on its speed.
         Returns True if it updated a sprite, False otherwise
        """

        visible = types.get_flag(sprite, types.FLAG_VISIBLE)
        active = types.get_flag(sprite, types.FLAG_ACTIVE)
        if not active or not visible:
            print(f"Returning due to active:{active} / visible: {visible}")
            return False

        if SpriteType.get_flag(sprite, FLAG_PHYSICS):
            self.phy.apply_speed(sprite, elapsed)

        # sprite.draw_x = int(new_x)
        # sprite.draw_y = int(new_y)

        if self.debug_inst:
            print("2D UPDATE SPRITE:")
            # print(f"  Pos {pos}")
            print(f"  Dir {dir}")
            print(f"  Speed {sprite.speed}")
            print(f"  Elapsed {elapsed}")
            # print(f"  New_x, new_y {[new_x,new_y]}")
            print(f"  FORMULA: new_y += sprite.speed * dir_y * elapsed")

        return True

    def is_within_bounds(self, coords):
        x, y = coords
        return is_point_within_bounds([x, y], self.bounds)

