from sprites.sprite_types import SpriteType, SPRITE_TEST_HEART

class TestSkull(SpriteType):
    name = SPRITE_TEST_HEART
    image_path = "/img/skull_16.bmp"
    width = 16
    height = 16
    color_depth = 4
    alpha_color = 0x0
    dot_color = 0x0000FF