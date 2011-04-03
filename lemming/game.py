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

        self.head_frame.pos += self.head_frame.vel * dt
        self.updateSpritePos(first.sprite, self.head_frame.pos)

        # apply input to physics
        acceleration = 200
        if self.control_state[Game.Control.MoveLeft]:
            self.head_frame.vel.x -= acceleration * dt
        if self.control_state[Game.Control.MoveRight]:
            self.head_frame.vel.x += acceleration * dt

        # prepare sprites for drawing
        start = self.absPt(Vec2d(0, 0)) / (tiles.width, tiles.height)
        end = self.absPt(Vec2d(self.window.width, self.window.height)) / Game.tile_size
        start.floor()
        end.floor()
        it = Vec2d(0, 0)
        for it.y in range(start.y, end.y):
            for it.x in range(start.x, end.x):
                sq = self.level.getSquare(it)
                if sq is not None and sq.sprite is not None:
                    self.updateSpritePos(sq.sprite, it * Game.tile_size)

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

        # draw tiles
        self.batch.draw()

        self.fps_display.draw()

    def absPt(self, rel_pt):
        return rel_pt / self.zoom + self.scroll

    def relPt(self, abs_pt):
        return (abs_pt - self.scroll) * self.zoom

    def _createWindow(self):
        self.window = pyglet.window.Window(width=1152, height=648, vsync=False)
        self.window.set_handler('on_draw', self.on_draw)
        self.window.set_handler('on_key_press', self.on_key_press)
        self.window.set_handler('on_key_release', self.on_key_release)

        pyglet.clock.schedule_interval(self.update, 1/Game.target_fps)
        self.fps_display = pyglet.clock.ClockDisplay()

    def execute(self):
        self._createWindow()

        pyglet.app.run()
