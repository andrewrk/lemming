from __future__ import division, print_function, unicode_literals
range = xrange

import tiles
import data
from vec2d import Vec2d
from level import Level

import pyglet
import sys

class Game(object):
    class Control:
        MoveLeft = 0
        MoveRight = 1
        Jump = 2

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


    target_fps = 60
    tile_size = (tiles.width, tiles.height)
    lemming_count = 9
    lemming_response_time = 0.10

    def loadImages(self):
        tileset = pyglet.image.load('tiles', file=data.load("tiles.bmp"))
        for tile in tiles.info.values():
            tile.image = tileset.get_region(tile.x*tiles.width, tile.y*tiles.height, tiles.width, tiles.height)
        self.lem_img = pyglet.image.load('lem', file=data.load("lem.png"))

        self.batch = pyglet.graphics.Batch()
        self.group_bg = pyglet.graphics.OrderedGroup(0)
        self.group_char = pyglet.graphics.OrderedGroup(1)
        self.group_fg = pyglet.graphics.OrderedGroup(2)

    def loadConfig(self):
        self.controls = {
            pyglet.window.key.LEFT: Game.Control.MoveLeft,
            pyglet.window.key.RIGHT: Game.Control.MoveRight,
            pyglet.window.key.UP: Game.Control.Jump,
        }

    def __init__(self):
        self.loadImages()
        self.loadConfig()
        self.clearLevel()

    def clearLevel(self):
        self.level = Level(self.batch, self.group_bg)
        self.scroll = Vec2d(0, 0)
        self.zoom = 1
        self.lemmings = [None] * Game.lemming_count
        self.control_state = [False] * (len(dir(Game.Control)) - 2)

    def start(self):
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


    def update(self, dt):
        first = self.lemmings[0]
        self.head_frame = Game.LemmingFrame(Vec2d(first.frame.pos), Vec2d(first.frame.vel), self.head_frame)

        for lemming in self.lemmings:
            lemming.frame = lemming.frame.prev_node
            self.updateSpritePos(lemming.sprite, lemming.frame.pos)
        self.lemmings[-1].frame.next_node = None

        # collision with solid blocks
        new_pos = self.head_frame.pos + self.head_frame.vel * dt
        block_there = (Vec2d(new_pos.x + tiles.width / 2, new_pos.y) / Game.tile_size).floored()
        tile_there = self.level.getTile(block_there)
        if tile_there.solid:
            new_pos.y = (block_there.y+1)*tiles.height
            self.head_frame.vel.y = 0

        # apply velocity to position
        self.head_frame.pos = new_pos
        self.updateSpritePos(first.sprite, self.head_frame.pos)

        # scroll the level
        self.scroll = Vec2d(self.head_frame.pos)
        if self.scroll.x < 0:
            self.scroll.x = 0
        self.scroll -= Vec2d(self.window.width, self.window.height) / 2

        # apply input to physics
        acceleration = 400
        if self.control_state[Game.Control.MoveLeft]:
            self.head_frame.vel.x -= acceleration * dt
        if self.control_state[Game.Control.MoveRight]:
            self.head_frame.vel.x += acceleration * dt

        on_ground = self.tileAt(Vec2d(self.head_frame.pos.x + tiles.width / 2, self.head_frame.pos.y-1)).solid

        # gravity
        gravity_accel = 800
        if not on_ground:
            self.head_frame.vel.y -= gravity_accel * dt

        def sign(n):
            if n > 0:
                return 1
            elif n < 0:
                return -1
            else:
                return 0
        # friction
        friction_accel = 50
        if on_ground:
            if abs(self.head_frame.vel.x) < abs(friction_accel * dt):
                self.head_frame.vel.x = 0
            else:
                self.head_frame.vel.x += friction_accel * dt * -sign(self.head_frame.vel.x)

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

    def updateSpritePos(self, sprite, abs_pos):
        pt = self.relPt(abs_pos)
        sprite.set_position(*pt)

    def on_key_press(self, symbol, modifiers):
        try:
            self.control_state[self.controls[symbol]] = True
        except KeyError:
            pass

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
