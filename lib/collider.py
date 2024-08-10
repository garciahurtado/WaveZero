from micropython import const

class Collider:
    on_crash_callback = None

    def __init__(self, player, sprite_manager, crash_y_start=const(48), crash_y_end=const(62)):
        self.player = player
        self.sprite_manager = sprite_manager
        self.crash_y_start = crash_y_start
        self.crash_y_end = crash_y_end

    def is_collision(self, colliders):
        """
        Check for collisions between the player and other sprites.

        :param colliders: List of active sprites to check for collisions.
        :return: True if a collision occurred, False otherwise.
        """
        if not self.player.visible or not self.player.active or not self.player.has_physics:
            return False

        for sprite in colliders:
            if (
                    (sprite.draw_y >= self.crash_y_start) and
                    (sprite.draw_y < self.crash_y_end) and
                    (self.sprite_manager.get_lane(sprite) == self.player.current_lane) and
                    self.player.has_physics
            ):
                print(f"Crash on {self.player.current_lane}")
                self.on_crash_callback()
                return True

        return False

    def _is_collision(self, sprite):
        """
        Check if a specific sprite collides with the player.

        :param sprite: The sprite to check for collision.
        :return: True if there's a collision, False otherwise.
        """
        return

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