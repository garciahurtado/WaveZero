from sprites.sprite_types import SpriteType, SPRITE_TEST_HEART

class TestHeart(SpriteType):
    name = SPRITE_TEST_HEART
    image_path = "/img/test_heart.bmp"
    width = 16
    height = 16
    color_depth = 4
    alpha_color = 0x0

    dot_color = 0x0000FF