from sprites2.sprite_types import SpriteType

class MemoryManager():
    addr_cache: {}
    cache_max_items = 0
    read_addrs: []
    write_addrs: []
    sprite: SpriteType

    def __init__(self):
        pass

    def init_sprite(self, sprite: SpriteType):
        self.sprite = sprite