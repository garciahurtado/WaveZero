from sprites2.sprite_manager import SpriteManager
from sprites2.sprite_types import SpriteType as types


class SpriteManager2D(SpriteManager):
    """ Specialized version of SpriteManager that doesnt need to do any 3D projections (although the parent-child
    hierarchy should probably be the other way around)"""
    
    def update_sprite(self, sprite, meta, elapsed):
        """The update function only applies to a single sprite at a time, and it is responsible for killing expired
        / out of bounds sprites, as well as updating the x and y draw coordinates based on the 3D position and camera view
        """
        visible = types.get_flag(sprite, types.FLAG_VISIBLE)
        active = types.get_flag(sprite, types.FLAG_ACTIVE)

        if not active or not visible:
            return False

        sprite.draw_x = int(sprite.x)
        sprite.draw_y = int(sprite.x)

        return True