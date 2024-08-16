from micropython import const

class Collider:
    on_crash_callback = None

    def __init__(self, player, sprite_manager, crash_y_start=const(46), crash_y_end=const(62)):
        self.player = player
        self.sprite_manager = sprite_manager
        self.crash_y_start = crash_y_start
        self.crash_y_end = crash_y_end

    def is_collision(self, colliders):
        """
        Check for collisions between the player and other sprites using lane bitmasks.

        :param colliders: List of active sprites to check for collisions.
        :return: True if a collision occurred, False otherwise.
        """
        if not self.player.visible or not self.player.active or not self.player.has_physics:
            return False

        player_lane_mask = self.player.lane_mask

        binary = bin(player_lane_mask)[2:]
        # print(f"lane mask: {binary}")

        for sprite in colliders:
            if (self.crash_y_start <= sprite.draw_y < self.crash_y_end and
                sprite.lane_mask & player_lane_mask):  # Bitwise AND to check lane overlap

                    print(f"Crash detected. Player lane: {self.player.current_lane}, ")
                    print(f"Sprite lanes: {bin(sprite.lane_mask)}")
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
#
#     def update_loop(self):
#         ...
#         if not self.paused:
#             ...
#             if self.collider.check_collisions(self.sprites.pool.active_sprites):
#                 self.do_crash()
#         ...
#
#     def do_crash(self):
#         # Implementation of crash handling
#         ...