from profiler import prof, timed
from scaler.const import DEBUG_PHYSICS, DEBUG, INK_CYAN, DEBUG_INST, DEBUG_UPDATE
from scaler.scaler_debugger import printc
from sprites.sprite_manager import SpriteManager
from sprites.sprite_types import SpriteType as types, FLAG_PHYSICS, FLAG_ACTIVE, FLAG_VISIBLE

class SpriteManager2D(SpriteManager):
    """ Specialized version of SpriteManager that doesnt need to do any 3D projections (although the parent-child
    hierarchy should probably be the other way around)
    """
    last_update_ms = 0

    #@timed
    def update_sprite(self, sprite, meta, elapsed):
        """ Updates a single sprite over an 'elapsed' time, by updating the x and y draw coordinates of the sprite based
        on its speed (or any other physics or time based effects). Returns True if it updated a sprite, False otherwise.
        It only works with thin / 2D sprites (ie: structs)
        """
        visible = types.get_flag(sprite, FLAG_VISIBLE)
        active = types.get_flag(sprite, FLAG_ACTIVE)

        if not active:
            self.pool.release(sprite, meta)
            return False

        if not visible:
            return True

        draw_x, draw_y = self.phy.get_draw_pos(sprite)
        sprite.draw_x = draw_x
        sprite.draw_y = draw_y
        # self.set_draw_xy(sprite, meta.height)

        # Check for out of bounds x or y. This should probably be integrated with the clipping logic in sprite_scaler
        if sprite.draw_x < self.min_draw_x:
            self.pool.release(sprite, meta)
            return False
        if sprite.draw_x > self.display.width - 1:
            self.pool.release(sprite, meta)
            return False

        """ Check that draw_y is within bounds """
        if sprite.draw_y < self.min_draw_y:
            self.pool.release(sprite, meta)
            return False
        elif sprite.draw_y > self.display.height - 1:
            self.pool.release(sprite, meta)
            return False

        """ Add some useful debugging statements """
        if DEBUG_UPDATE:
            printc(f"SPRITE 2D UPDATE :", INK_CYAN)
            print(f"draw_x: {sprite.draw_x}, draw_y: {sprite.draw_y}")
            print(f"scale: {sprite.scale}")
            print(f"speed: {sprite.speed}")
            print(f"elapsed: {elapsed}")
            print(f"active: {active}")
            print(f"visible: {visible}")

        return True

    def set_draw_xy(self, sprite, sprite_height=16, scale: float = 1):
        """ For now, the 2D sprite manager only copies coordinates of the sprite to the draw coordinates."""
        sprite.draw_x = sprite.x
        sprite.draw_y = sprite.y
