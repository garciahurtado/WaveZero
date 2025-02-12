from sprites2.sprite_types import SpriteType, SPRITE_GAMEBOY

class GameboySprite(SpriteType):
    name = SPRITE_GAMEBOY
    image_path = "/img/gameboy.bmp"
    width = 16
    height = 16
    color_depth = 4
    alpha_color = 0x0
