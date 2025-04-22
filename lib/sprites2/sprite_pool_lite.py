from typing import List

import utime
from uarray import array

from dump_object import dump_object
from sprites2.sprite_types import create_sprite, SPRITE_DATA_LAYOUT, SPRITE_DATA_SIZE, SpriteType, FLAG_PHYSICS
from sprites2.sprite_types import FLAG_VISIBLE, FLAG_ACTIVE
from uctypes import addressof, struct
from profiler import Profiler as prof
from scaler.const import DEBUG_POOL

POOL_CHUNK_SIZE = 50

class PoolNode:
    """ Implements a linked list for easy iterating of the sprite pool """
    __slots__ = ['sprite', 'index', 'prev', 'next']

    def __init__(self, sprite, index, prev=None, next=None):
        self.sprite = sprite
        self.index = index
        self.prev = prev
        self.next = next

class SpritePool:
    pool_size: int
    all_indices = 0
    free_count = 0
    active_count = 0
    head = None
    tail = None
    pool_nodes: List[PoolNode] = []
    sprites: List[struct] = []
    sprite_memory: List[bytearray] = []
    mgr = None

    def __init__(self, pool_size):
        self.pool_size = pool_size
        print(f"About to create sprite pool of {pool_size} (typeless)")

        self.create_pool(pool_size)

        self.all_indices = array('H', range(pool_size))  # Unsigned short array for ALL sprite indices
        self.ready_indices = array('H', range(pool_size))  # Unsigned short array for INACTIVE / READY sprite indices
        self.free_count = int(pool_size)

    def create_pool(self, pool_size):
        """ Initialize sprite memory """
        self.sprite_memory = []

        """ "chunk" is an integer number of sprites in a single, contiguous, byte array"""
        # chunk_size = min(pool_size, POOL_CHUNK_SIZE)
        # for i in range(0, pool_size, chunk_size):
        #     chunk = bytearray(SPRITE_DATA_SIZE * min(chunk_size, pool_size - i))
        #     self.sprite_memory.append(chunk)

        # Create sprite structures
        # self.sprites = []
        # # for i, chunk in enumerate(self.sprite_memory):
        # #     for j in range(len(chunk) // SPRITE_DATA_SIZE):
        #         addr = uctypes.addressof(chunk) + j * SPRITE_DATA_SIZE
        #
        #         self.sprites.append(new_sprite)
        #         new_node = PoolNode(sprite=new_sprite)
        #         self.pool_nodes.append(PoolNode)

        for s in range(self.pool_size):
            # Create the sprite in memory
            addr = addressof(bytearray(SPRITE_DATA_SIZE))
            new_sprite = struct(addr, SPRITE_DATA_LAYOUT)
            self.sprites.append(new_sprite)

            # Create the node to hold it in the pool
            node = PoolNode(sprite=new_sprite, index=s)
            self.pool_nodes.append(node)


    def get(self, sprite_type, meta):
        """ TODO: theres a problem here with the fact that we have two ways to determine a sprite is active:
        - sprite.active = True
        - belongs to self.active_indices
        """
        """Get the first sprite available from the pool and return it"""
        """ sprite_type: int
            meta: SpriteType
        
        """

        if self.free_count < 1:
            raise RuntimeError("Sprite pool is empty. Consider increasing pool size.")

        """ We do this at the start to prevent possible race conditions """
        self.free_count = self.free_count - 1

        index = self.ready_indices[self.free_count]
        node = self.pool_nodes[index]
        sprite = node.sprite

        if DEBUG_POOL:
            print(f".get() - {len(self.all_indices)} total indices / free_count={self.free_count} ")
            print(f".ready index will be {index} for sprite {sprite}")

        sprite.sprite_type = sprite_type # int
        sprite.current_frame = 0

        sprite.born_ms = int(utime.ticks_ms()) # reset creation timestamp

        # Use the new flag system instead of separate active and visible fields
        SpriteType.set_flag(sprite, FLAG_ACTIVE)
        SpriteType.set_flag(sprite, FLAG_VISIBLE)

        # Only active sprites in this queue
        if not self.head:
            self.head = self.tail = node
        else:
            node.next = self.head
            self.head.prev = node
            self.head = node

        self.active_count += 1

        prof.start_profile('pool.reset')
        # print(type(meta))
        # print(meta)
        # print(dir(meta))
        #
        # print(type(sprite))
        # print(sprite)

        meta.reset(sprite)

        prof.end_profile('pool.reset')

        return sprite, index

    def release(self, sprite, meta):
        """ Take a sprite out of commission, so that it stops being updated, and it becomes available for recycling"""
        meta.unset_flag(sprite, FLAG_ACTIVE)
        meta.unset_flag(sprite, FLAG_VISIBLE)
        meta.unset_flag(sprite, FLAG_PHYSICS)

        # Find and remove the node from the linked list
        current = self.head
        while current:
            if current.sprite is sprite:
                if current.prev:
                    current.prev.next = current.next
                else:
                    self.head = current.next

                if current.next:
                    current.next.prev = current.prev
                else:
                    self.tail = current.prev

                break
            current = current.next

        self.active_count -= 1

        # Add the index back to free_indices
        idx = self.sprites.index(sprite)
        self.ready_indices[self.free_count] = idx
        self.free_count += 1

        return idx

    def insert(self, sprite, position):
        """ DEPRECATED """
        if position < 0 or position > self.active_count:
            raise ValueError("Invalid position for insertion")

        new_node = PoolNode(sprite, self.sprites.index(sprite))

        if position == 0:
            new_node.next = self.head
            if self.head:
                self.head.prev = new_node
            self.head = new_node
            if not self.tail:
                self.tail = new_node
        elif position == self.active_count:
            new_node.prev = self.tail
            if self.tail:
                self.tail.next = new_node
            self.tail = new_node
            if not self.head:
                self.head = new_node
        else:
            current = self.head
            for _ in range(position):
                current = current.next
            new_node.prev = current.prev
            new_node.next = current
            current.prev.next = new_node
            current.prev = new_node

        self.active_count += 1

    def active_sprites_forward(self):
        current = self.head
        while current:
            yield current.sprite
            current = current.next

    def active_sprites_backward(self):
        current = self.tail
        while current:
            yield current.sprite
            current = current.prev

    @property
    def active_sprites(self):
        return self.active_sprites_forward()

    def __len__(self):
        """Return the number of active sprites"""
        return int(self.active_count)

