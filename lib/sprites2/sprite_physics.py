"""
In order to store floating point as fixed point 16bit ints:

With FP_SHIFT=5:
- 1 sign bit
- 10 bits for integer (2^10 = 1024 possible values)
- 5 bits for fraction (2^5 = 32 divisions = 0.03125 precision)

With FP_SHIFT=14:
- 1 sign bit
- 1 bit for integer (2^1 = 2 possible values)
- 14 bits for fraction (2^14 = 16384 divisions = 0.00006103515625 precision)

Example for 123.25:
Binary: 0000011110.10000
    |     |      |
    |   Integer  |
Sign bit      Fraction

---

# To represent 1.5 in fixed point


# Example scaling:
x = 100 << FP_SHIFT  # Convert 100 to fixed point
scaled_x = (x * FP_SCALE) >> FP_SHIFT  # Scale by 1.5
"""
from sprites2.sprite_types import SpriteType

""" For general fixed-point variables (-2048.0 to +2047.9375 range) """
FP_SHIFT = 4
FP_ONE = (1 << FP_SHIFT)  # = 16 (1.0 in fixed point)
FP_SCALE = int(1.5 * FP_ONE)  # = 24 (1.5 in fixed point)

""" For -3.142 to +3.142 range (±π radians) """
FP_SHIFT_RAD = 11
FP_ONE_RAD = (1 << FP_SHIFT_RAD)  # = 2048 (1.0 in fixed point)
FP_SCALE_RAD = int(1.5 * FP_ONE_RAD)  # = 3072 (1.5 in fixed point)
class SpritePhysics:
    debug = False

    def __init__(self):
        pass

    @staticmethod
    def get_pos(inst):
        """ Convert fixed point coordinates to display integers. These coords point to the center of the sprite """
        x = inst.x >> FP_SHIFT
        y = inst.y >> FP_SHIFT
        return x, y

    @staticmethod
    def set_pos(inst, x, y):
        """ Convert float coordinates to fixed point """
        inst.x = int(x * (1 << FP_SHIFT))
        inst.y = int(y * (1 << FP_SHIFT))
        return True

    @staticmethod
    def get_dir(inst):
        """ Convert fixed point direction vector to floats """
        dir_x = inst.dir_x / (1 << FP_SHIFT_RAD)
        dir_y = inst.dir_y / (1 << FP_SHIFT_RAD)
        return dir_x, dir_y

    @staticmethod
    def set_dir(inst, dir_x, dir_y):
        """ Convert float direction vector to fixed point """
        inst.dir_x = int(dir_x * (1 << FP_SHIFT_RAD))
        inst.dir_y = int(dir_y * (1 << FP_SHIFT_RAD))
        return True

    @staticmethod
    def apply_speed(sprite, elapsed):

        """ Based on the time passed, apply the speed and direction to the position of this sprite """
        old_x, old_y = SpritePhysics.get_pos(sprite)
        dir_x, dir_y = SpritePhysics.get_dir(sprite)
        new_x = old_x + (sprite.speed * dir_x * elapsed)
        new_y = old_y + (sprite.speed * dir_y * elapsed)

        if SpritePhysics.debug:
            print(f"* APPLY SPEED sprite:{sprite}, elapsed: {elapsed}, speed: {sprite.speed}")
            print(f"\t dir_x, dir_y x:{dir_x}, y: {dir_y}")
            print(f"\t new_x, new_y x:{new_x}, y: {new_y}")

        if ([int(old_x), int(old_y)] == [int(new_x), int(new_y)]):
            if SpritePhysics.debug:
                print("Returning without updating sprite")

        SpritePhysics.set_pos(sprite, new_x, new_y)

    @staticmethod
    def get_draw_pos(sprite, scaled_width, scaled_height, scaled=False):
        draw_x, draw_y = SpritePhysics.get_pos(sprite)

        """ Since sprite x/y indicate the center of the sprite, we offset the draw origin left and up relative to half 
        the sprite dimensions. """
        draw_x += -(scaled_width / 2)
        draw_y += -(scaled_height / 2)

        return int(draw_x), int(draw_y)




