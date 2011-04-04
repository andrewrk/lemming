from __future__ import division, print_function, unicode_literals
range = xrange

import tiles
import data
from vec2d import Vec2d
from level import Level

import pyglet
import sys

def sign(n):
    if n > 0:
        return 1
    elif n < 0:
        return -1
    else:
        return 0

class Game(object):
    class Control:
        MoveLeft = 0
        MoveRight = 1
        Jump = 2
        BellyFlop = 3
        Freeze = 4
        Explode = 5

    class LemmingFrame(object):
        def __init__(self, pos, vel, next_node):
            self.pos = pos
            self.vel = vel
            self.next_node = next_node
            self.prev_node = None
            
            if self.next_node is not None:
                self.next_node.prev_node = self

    class Lemming(object):
        def __init__(self, sprite, frame=None):
            self.sprite = sprite
            self.frame = frame
            self.gone = False


    target_fps = 60
    tile_size = Vec2d(tiles.width, tiles.height)
    lemming_count = 9
    lemming_response_time = 0.20

    def loadImages(self):
        tileset = pyglet.image.load('tiles', file=data.load("tiles.png"))
        for tile in tiles.info.values():
            tile.image = tileset.get_region(tile.x*tiles.width, tile.y*tiles.height, tiles.width, tiles.height)
        self.lem_img = pyglet.image.load('lem', file=data.load("lem.png"))

        self.img_bg = pyglet.image.load('img_bg', file=data.load("background.png"))
        self.img_bg_hill = pyglet.image.load('img_bg_hill', file=data.load("hill.png"))

        self.batch = pyglet.graphics.Batch()
        self.group_bg2 = pyglet.graphics.OrderedGroup(0)
        self.group_bg1 = pyglet.graphics.OrderedGroup(1)
        self.group_level = pyglet.graphics.OrderedGroup(2)
        self.group_char = pyglet.graphics.OrderedGroup(3)
        self.group_fg = pyglet.graphics.OrderedGroup(4)

        self.sprite_bg_left = pyglet.sprite.Sprite(self.img_bg, batch=self.batch, group=self.group_bg2)
        self.sprite_bg_right = pyglet.sprite.Sprite(self.img_bg, batch=self.batch, group=self.group_bg2)
        self.sprite_hill_left = pyglet.sprite.Sprite(self.img_bg_hill, batch=self.batch, group=self.group_bg1)
        self.sprite_hill_right = pyglet.sprite.Sprite(self.img_bg_hill, batch=self.batch, group=self.group_bg1)

    def loadConfig(self):
        self.controls = {
            pyglet.window.key.LEFT: Game.Control.MoveLeft,
            pyglet.window.key.RIGHT: Game.Control.MoveRight,
            pyglet.window.key.UP: Game.Control.Jump,
            pyglet.window.key._1: Game.Control.BellyFlop,
            pyglet.window.key._2: Game.Control.Freeze,
            pyglet.window.key._3: Game.Control.Explode,
        }

    def __init__(self):
        self.loadImages()
        self.loadConfig()
        self.clearLevel()

    def clearLevel(self):
        self.level = Level(self.batch, self.group_level)
        self.scroll = Vec2d(0, 0)
        self.scroll_vel = Vec2d(0, 0)
        self.zoom = 1
        self.lemmings = [None] * Game.lemming_count
        self.control_state = [False] * (len(dir(Game.Control)) - 2)

    def start(self):
        self.control_lemming = 0
        self.explode_queued = False # true when the user presses the button until an update happens
        self.bellyflop_queued = False
        self.freeze_queued = False
        self.plus_ones_queued = 0

        # resets variables based on level and begins the game
        # generate data for each lemming
        for i in range(len(self.lemmings)):
            sprite = pyglet.sprite.Sprite(self.lem_img, batch=self.batch, group=self.group_char)
            if i > 0:
                sprite.opacity = 128
            self.lemmings[i] = Game.Lemming(sprite, None)

        # generate frames for trails
        self.head_frame = Game.LemmingFrame(Vec2d(self.level.start), Vec2d(0, 0), None)
        lemming_index = len(self.lemmings) - 1
        self.lemmings[lemming_index].frame = self.head_frame
        lemming_index -= 1
        lemming_frame_count = 1
        while Game.target_fps * Game.lemming_response_time * (len(self.lemmings)-1) > lemming_frame_count:
            self.head_frame = Game.LemmingFrame(Vec2d(self.level.start), Vec2d(0, 0), self.head_frame)
            lemming_frame_count += 1
            if int((len(self.lemmings) - 1 - lemming_index) * Game.target_fps * Game.lemming_response_time) == lemming_frame_count:
                self.lemmings[lemming_index].frame = self.head_frame
                lemming_index -= 1

    def detatchHeadLemming(self):
        self.control_lemming += 1
        self.lemmings[self.control_lemming].sprite.opacity = 255
        self.head_frame = self.lemmings[self.control_lemming].frame

    def update(self, dt):
        # detach head lemming from the rest
        if self.explode_queued:
            self.explode_queued = False
            self.detatchHeadLemming()

        # add more lemmings
        while self.plus_ones_queued > 0 and self.control_lemming > 0:
            self.plus_ones_queued -= 1
            print('add 1 lemming')

        # lemming trails
        char = self.lemmings[self.control_lemming]
        self.head_frame = Game.LemmingFrame(Vec2d(char.frame.pos), Vec2d(char.frame.vel), self.head_frame)

        for lemming in self.lemmings[self.control_lemming:]:
            lemming.frame = lemming.frame.prev_node
            self.updateSpritePos(lemming.sprite, lemming.frame.pos)
        self.lemmings[-1].frame.next_node = None

        for lemming in self.lemmings[:self.control_lemming+1]:
            if lemming.gone:
                continue

            frame = lemming.frame
            # collision with solid blocks
            new_pos = frame.pos + frame.vel * dt
            block_there = (Vec2d(new_pos.x + tiles.width / 2, new_pos.y) / Game.tile_size).floored()
            tile_there = self.level.getTile(block_there)
            if tile_there.solid:
                new_pos.y = (block_there.y+1)*tiles.height
                frame.vel.y = 0

            # apply velocity to position
            frame.pos = new_pos

            on_ground = self.tileAt(Vec2d(frame.pos.x + tiles.width / 2, frame.pos.y-1)).solid

            if lemming == char:
                # item pickups
                feet_block = ((frame.pos + Game.tile_size / 2) / Game.tile_size).floored()
                head_block = feet_block + Vec2d(0, 1)
                feet_tile = self.level.getTile(feet_block)
                head_tile = self.level.getTile(head_block)
                # +1
                if self.control_lemming > 0:
                    if head_tile.id == tiles.enum.PlusOne:
                        self.plus_ones_queued += 1
                        self.level.setTile(head_block, tiles.enum.Air)
                    elif feet_tile.id == tiles.enum.PlusOne:
                        self.plus_ones_queued += 1
                        self.level.setTile(feet_block, tiles.enum.Air)


                # scroll the level
                desired_scroll = Vec2d(frame.pos)
                if desired_scroll.x < 0:
                    desired_scroll.x = 0
                desired_scroll -= Vec2d(self.window.width, self.window.height) / 2
                xdist1 = desired_scroll.x - self.scroll.x
                ydist1 = desired_scroll.y - self.scroll.y
                self.scroll.x += xdist1 * Game.target_fps * 0.15 * dt
                self.scroll.y += ydist1 * Game.target_fps * 0.15 * dt

                # apply input to physics
                acceleration = 500
                max_speed = 200
                if self.control_state[Game.Control.MoveLeft]:
                    if frame.vel.x - acceleration * dt < -max_speed:
                        frame.vel.x = -max_speed
                    else:
                        frame.vel.x -= acceleration * dt
                if self.control_state[Game.Control.MoveRight]:
                    if frame.vel.x + acceleration * dt > max_speed:
                        frame.vel.x = max_speed
                    else:
                        frame.vel.x += acceleration * dt
                if self.control_state[Game.Control.Jump] and on_ground:
                    jump_velocity = 350
                    frame.vel.y = jump_velocity

            # gravity
            gravity_accel = 800
            if not on_ground:
                frame.vel.y -= gravity_accel * dt

            # friction
            friction_accel = 150
            if on_ground:
                if abs(frame.vel.x) < abs(friction_accel * dt):
                    frame.vel.x = 0
                else:
                    frame.vel.x += friction_accel * dt * -sign(frame.vel.x)

        # prepare sprites for drawing
        start = self.absPt(Vec2d(0, 0)) / Game.tile_size
        end = self.absPt(Vec2d(self.window.width, self.window.height)) / Game.tile_size
        start.floor()
        end.floor()
        it = Vec2d(0, 0)
        for it.y in range(start.y-5, end.y+5):
            for it.x in range(start.x-5, end.x+5):
                sq = self.level.getSquare(it)
                if sq is not None and sq.sprite is not None:
                    pos = it * Game.tile_size
                    self.updateSpritePos(sq.sprite, pos)
                    sq.sprite.scale = self.zoom

        # background sprites
        far_bgpos = Vec2d(-((self.scroll.x * 0.25) % self.sprite_bg_left.width), -(self.scroll.y * 0.10))
        if far_bgpos.y > 0:
            far_bgpos.y = 0
        if far_bgpos.y + self.sprite_bg_left.height < self.window.height:
            far_bgpos.y = self.window.height - self.sprite_bg_left.height
        self.sprite_bg_left.set_position(*far_bgpos)
        self.sprite_bg_right.set_position(far_bgpos.x + self.sprite_bg_right.width, far_bgpos.y)

        close_bgpos = Vec2d(-((self.scroll.x * 0.5) % self.sprite_hill_left.width), -(self.scroll.y * 0.20))
        if close_bgpos.y > 0:
            close_bgpos.y = 0
        self.sprite_hill_left.set_position(*close_bgpos)
        self.sprite_hill_right.set_position(close_bgpos.x + self.sprite_hill_right.width, close_bgpos.y)

        # lemmings
        for lemming in self.lemmings:
            self.updateSpritePos(lemming.sprite, lemming.frame.pos)

    def updateSpritePos(self, sprite, abs_pos):
        pt = self.relPt(abs_pos)
        sprite.set_position(*pt)

    def on_key_press(self, symbol, modifiers):
        try:
            control = self.controls[symbol]
            self.control_state[control] = True
        except KeyError:
            return
        if control == Game.Control.Explode:
            self.explode_queued = True
        elif control == Game.Control.BellyFlop:
            self.bellyflop_queued = True
        elif control == Game.Control.Freeze:
            self.freeze_queued = True


    def on_key_release(self, symbol, modifiers):
        try:
            self.control_state[self.controls[symbol]] = False
        except KeyError:
            pass

    def on_draw(self):
        self.window.clear()
        self.batch.draw()
        self.fps_display.draw()

    def absPt(self, rel_pt):
        return rel_pt / self.zoom + self.scroll

    def relPt(self, abs_pt):
        return (abs_pt - self.scroll) * self.zoom

    def tileAt(self, abs_pt):
        return self.level.getTile((abs_pt / Game.tile_size).floored())

    def _createWindow(self):
        self.window = pyglet.window.Window(width=853, height=480, vsync=False)
        self.window.set_handler('on_draw', self.on_draw)
        self.window.set_handler('on_key_press', self.on_key_press)
        self.window.set_handler('on_key_release', self.on_key_release)

        pyglet.clock.schedule_interval(self.update, 1/Game.target_fps)
        self.fps_display = pyglet.clock.ClockDisplay()

    def execute(self):
        self._createWindow()

        pyglet.app.run()
