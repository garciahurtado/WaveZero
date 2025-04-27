from uarray import array

from sprites.sprite_types import SpriteType

class MemoryManager():
    addr_cache: None
    cache_max_items = 0
    read_addrs: []
    write_addrs: []
    write_addrs_all: {}
    write_addrs_curr = 0
    read_addr_max = 10
    read_cache = {}
    min_write_addr = 0
    sprite: SpriteType
    display_stride = 0
    display_stride_cache = {}

    def __init__(self, display):
        """ Create array with maximum possible number of read and write addresses """
        read_buf = bytearray((display.height + 2) * 4)  # why does this need to be +2?
        write_buf = bytearray((display.height + 2) * 4)

        # self.read_addrs = array('L', read_buf)
        # self.write_addrs = array('L', write_buf)
        # self.write_addrs_all = {}
        # self.read_cache = AddrCache(16, 64)

    def init_sprite(self, sprite: SpriteType, display_stride):
        self.sprite = sprite
        self.display_stride = display_stride

    def add_buffer(self, width):
        stride = width * 2
        self.display_stride_cache[width] = stride

    def select_size(self, size):
        self.write_addrs_curr = self.write_addrs_all[size]

    def _cache_write_addrs(self, frame_sizes):
        """ Generate and cache up to the maximum amount of write addresses (the height of the viewport) """

        for [height, width] in frame_sizes:
            write_base = self.min_write_addr

            display_stride = self.display_stride_cache[width]
            row_list = array("L", [0] * (height+1))

            curr_addr = write_base
            row_id = 0
            for row_id in range(height):
                row_list[row_id] = curr_addr
                curr_addr = self.next_write_addr(curr_addr, display_stride)

            """ Add null terminator """
            row_list[row_id+1] = 0x00000000
            self.write_addrs_all[height] = row_list

    def _fill_write_addrs(self, width, height):
        write_base = self.min_write_addr

        display_stride = self.display_stride_cache[width]
        display_stride = width * 2
        # row_list = array("L", [0] * (height + 1))

        curr_addr = write_base
        row_id = 0
        for row_id in range(height):
            self.write_addrs[row_id] = curr_addr
            curr_addr = self.next_write_addr(curr_addr, display_stride)

        """ Add null terminator """
        self.write_addrs[row_id + 1] = 0x00000000
        # self.write_addrs_all[height] = row_list

    def next_write_addr(self, curr_addr, stride):
        next_addr = curr_addr + stride
        return next_addr




