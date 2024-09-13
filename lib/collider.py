from micropython import const


class Collider:
    on_crash_callback = None

    def __init__(self, player, sprite_manager, crash_y_start, crash_y_end):
        self.player = player
        self.sprite_manager = sprite_manager
        self.crash_y_start = crash_y_start
        self.crash_y_end = crash_y_end

    def check_collisions(self, collide_against):
        """
        Check for collisions between the player and other sprites using lane bitmasks.

        :param collide_against: List of sprites to check for collisions.
        :return: True if a collision occurred, False otherwise.
        """
        if not self.player.visible or not self.player.active or not self.player.has_physics:
            return False

        player_lane_mask = self.player.lane_mask

        for sprite in collide_against:
            # print(f"CHeck against {sprite} - {self.crash_y_start} <= {sprite.draw_y} < {self.crash_y_end}")
            # We use Bitwise AND between the two lane_masks to check for overlap
            if (self.crash_y_start <= sprite.draw_y < self.crash_y_end and
                    sprite.lane_mask & player_lane_mask):
                self.on_crash_callback()
                return True

        return False

    def add_callback(self, callback):
        self.on_crash_callback = callback

# Example usage in SpriteMgrTestScreen:
#
# class SpriteMgrTestScreen(GameScreen):
#     def __init__(self, display, *args, **kwargs):
#         super().__init__(display, *args, **kwargs)
#         ...
#         self.crash_y_start = const(48)
#         self.crash_y_end = const(62)
#         self.collider = Collider(self.player, self.sprites, self.crash_y_start, self.crash_y_end)
#         self.collider.add_callback(self.do_crash)

#     def update_loop(self):
#         ...
#         if not self.paused:
#            self.collider.check_collisions(self.sprites.pool.active_sprites):
#
#     def do_crash(self):
#         # Implementation of crash handling
#         ...
