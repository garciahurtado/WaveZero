import random
import color_util as colors


def ground_laser(display, camera, from_x, from_y, x, y, z, sprite_width):
    if z < 200:
        line_colors = 0xFF0000, 0xF63800, 0xFF7C00, 0xFFBB00
        if random.randrange(0,2):
            return

        id = random.randrange(0, 4)

        line_color = colors.rgb_to_565(colors.hex_to_rgb(line_colors[id]))
        half_width = sprite_width // 2
        [to_x, to_y] = camera.to_2d(x+half_width, 0, z)

        display.line(to_x, from_y, to_x, to_y, line_color)
        # display.line(to_x+1, from_y, to_x+1, to_y, line_color)