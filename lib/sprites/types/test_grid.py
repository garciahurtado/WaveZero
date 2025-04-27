from sprites.sprite_types import SpriteType, SPRITE_TEST_GRID

class TestGrid(SpriteType):
    name = SPRITE_TEST_GRID
    image_path = "/img/test_16.bmp"
    width = 16
    height = 16
    color_depth = 4
    alpha_color = 0x0