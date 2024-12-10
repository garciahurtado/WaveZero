# sprite_scaler_test.py
"""Test harness matching original demo code"""
from scaler.dma_interp_scaler import SpriteScaler
from sprites2.test_square import TestSquare


def init_test_sprite_scaling(display):
    # Port original demo code here
    print()
    print(">>> INTERP Sprite scaling demo <<< ")
    print()
    print()

    # Test data has 1 pixel per byte, real data will have 2px/byte
    # sprite_data = bytearray([
    #     0b00000001, 0b00000011, 0b00000110, 0b00001100,
    #     0b00000101, 0b00000111, 0b00001101, 0b00011000,
    #     0b00001001, 0b00001011, 0b00011011, 0b00110000,
    #     0b00010001, 0b00010011, 0b00110111, 0b01100000,
    # ])

    """ 2px packed into 1 byte (8px x 4px image) """
    sprite_data = bytearray([
        0b00010000, 0b00100011, 0b00110010, 0b00000001,
        0b00000001, 0b00110010, 0b00100011, 0b00010000,
        0b00110010, 0b00000001, 0b00010000, 0b00100011,
        0b00100011, 0b00010000, 0b00000001, 0b00110010,
    ])
    # sprite = TestSprite(sprite_data, width=4, height=4)

    sprite = TestSquare()
    scaler = SpriteScaler(display)

    # for scale in [1, 2, 3]:
    # for scale in [1]:
    #     print()
    #     print(f"\n=== Testing {scale * 100}% scaling ===")
    #     scaler.debug = True
    #     scaler.draw_sprite(sprite, 1, scale)

    return sprite, scaler

class TestSprite():
    def __init__(self, sprite_data, width, height):
        self.pixel_bytes = sprite_data
        self.width = width
        self.height = height
        self.x = 0
        self.y = 0