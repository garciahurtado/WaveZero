from road_grid import RoadGrid as grid
from colors import color_util as colors


def show_colors():
    iter_colors(grid.horiz_palette)
    iter_colors(grid.horizon_palette)

def iter_colors(palette):
    for color in palette:
        rgb565 = colors.rgb_to_565(colors.hex_to_rgb(color))
        print(f"0x{rgb565:04x}")

    print()

show_colors()