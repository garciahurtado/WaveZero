from sprites2.sprite_types import SpriteType, SPRITE_TEST_SQUARE

class TestSquare(SpriteType):
    name = SPRITE_TEST_SQUARE
    image_path = "/img/test_checkered.bmp"
    width = 32
    height = 32
    color_depth = 4
    alpha = None
