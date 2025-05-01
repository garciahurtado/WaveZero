from anim.palette_rotate_one import PaletteRotateOne
from colors.color_util import BGR565
from scaler.const import DEBUG
from sprites.types.laser_wall import LaserWall
from sprites.types.warning_wall import WarningWall
from sprites.types.white_line import WhiteLine
from stages.events import Event
from stages.stage import Stage
from sprites.sprite_types import *
from colors.palettes import convert_hex_palette, PALETTE_FIRE
import micropython

class Stage1(Stage):
    base_speed = -200
    fire_palette = None
    shared_palette = None

    def __init__(self, sprite_manager):
        super().__init__(sprite_manager)

        spawn_z = 5000
        # spawn_z = 20
        spawn_z_step = 40
        line_height = 24

        # Times in ms
        med_wait = 10000
        small_wait = 1000
        tiny_wait = 500


        Event.sprite_manager = sprite_manager
        evt = self.events

        self.load_types()
        # self.init_palettes()

        # evt_list = []
        # for i in range(0):
        #     evt_list.append(evt.spawn(SPRITE_BARRIER_RIGHT_x2, lane=0, z=spawn_z))
        #     evt_list.append(evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z))
        #     spawn_z += spawn_z_step

        self.wait(3000)
        self.sequence([
            # evt.multi(evt_list),
            evt.multi([
                evt.spawn(SPRITE_BARRIER_LEFT, lane=0, z=spawn_z, speed=self.base_speed),
                evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z),
                evt.spawn(SPRITE_WHITE_LINE_VERT, lane=0, z=spawn_z),
                evt.spawn(SPRITE_WHITE_LINE_VERT, lane=5, z=spawn_z),
                evt.spawn(SPRITE_WHITE_LINE_VERT, lane=0, z=spawn_z, y=line_height),
                evt.spawn(SPRITE_WHITE_LINE_VERT, lane=5, z=spawn_z, y=line_height),
                evt.spawn(SPRITE_WHITE_LINE_x5, lane=0, z=spawn_z, y=line_height*2),
                evt.spawn(SPRITE_WHITE_LINE_VERT_x3, lane=3, z=spawn_z),

                evt.wait(tiny_wait)],
                repeat=16),
            evt.wait(small_wait)],
            repeat=2)

            # evt.multi([
            #     evt.spawn(SPRITE_BARRIER_RIGHT_x2, lane=0, z=spawn_z),
            #     evt.spawn(SPRITE_BARRIER_LEFT_x2, lane=3, z=spawn_z),
            #     evt.wait(tiny_wait)],
            #     repeat=16),
            # evt.wait(small_wait),

        # self.wait(500)
        # asyncio.create_task(self.rotate_palette())

    def init_palettes(self):
        """ This is just so that the image and palette will be loaded ahead of the spawns"""

        sprite, _ = self.sprite_manager.spawn(SPRITE_WHITE_LINE)
        shared_pal = self.sprite_manager.sprite_palettes[SPRITE_WHITE_LINE]
        self.fire_palette = convert_hex_palette(PALETTE_FIRE, color_mode=BGR565)

        sprite, _ = self.sprite_manager.spawn(SPRITE_WHITE_LINE_VERT)
        self.sprite_manager.sprite_palettes[SPRITE_WHITE_LINE_VERT] = shared_pal
        self.shared_palette = shared_pal

        print(micropython.mem_info())

        self.color_anim = PaletteRotateOne(self.shared_palette, self.fire_palette, 100, 0)
        self.color_anim.stop()

        print(micropython.mem_info())

        return True

    def load_types(self):
        mgr = self.sprite_manager
        mgr.add_type(
            sprite_type=SPRITE_BARRIER_LEFT,
            sprite_class=WarningWall,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_BARRIER_LEFT_x2,
            sprite_class=WarningWall,
            # speed=self.base_speed,
            speed=0,
            repeats=2,
            repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_BARRIER_RIGHT,
            sprite_class=WarningWall,
            image_path="/img/road_barrier_yellow_inv.bmp",
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_BARRIER_RIGHT_x2,
            image_path="/img/road_barrier_yellow_inv.bmp",
            sprite_class=WarningWall,
            speed=self.base_speed,
            repeats=2,
            repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_LASER_WALL,
            sprite_class=LaserWall,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_LASER_WALL_x2,
            sprite_class=LaserWall,
            repeats=2,
            repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_LASER_WALL_x5,
            sprite_class=LaserWall,
            repeats=5,
            repeat_spacing=24)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_x2,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            repeats=2,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_x5,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line.bmp",
            width=24,
            height=2,
            repeats=5,
            repeat_spacing=24,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT_x3,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            repeats=3,
            speed=self.base_speed)

        mgr.add_type(
            sprite_type=SPRITE_WHITE_LINE_VERT_x6,
            sprite_class=WhiteLine,
            image_path="/img/test_white_line_vert.bmp",
            width=2,
            height=24,
            repeats=6,
            repeat_spacing=24,
            speed=self.base_speed)

        # mgr.add_type(
        #     sprite_type=SPRITE_ALIEN_FIGHTER,
        #     sprite_class=AlienFighter,
        #     image_path="/img/alien_fighter.bmp",
        #     width=24,
        #     height=16,
        #     speed=0)


