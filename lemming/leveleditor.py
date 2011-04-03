from __future__ import division, print_function, unicode_literals
range = xrange

import pyglet
import tempfile
from level import Level
import os

from game import Game
import tiles
from vec2d import Vec2d

class LevelEditor(Game):
    class Mode:
        NORMAL = 0
        CHOOSE_TILE = 1
        PLAYTEST = 2

    
    def __init__(self, level_filename=None):
        super(LevelEditor, self).__init__()
        self.level_filename = level_filename

    def clearLevel(self):
        super(LevelEditor, self).clearLevel()

        self.grid_on = True

        self.mode = LevelEditor.Mode.NORMAL
        self.left_mouse_down = False
        self.right_mouse_down = False
        self.selected_tile = 0

    def update(self, dt):
        if self.mode == LevelEditor.Mode.PLAYTEST:
            super(LevelEditor, self).update(dt)

    def on_draw(self):
        self.window.clear()

        if self.mode == LevelEditor.Mode.NORMAL:
            # draw tiles
            start = self.absPt(Vec2d(0, 0)) / (tiles.width, tiles.height)
            end = self.absPt(Vec2d(self.window.width, self.window.height)) / Game.tile_size
            start.floor()
            end.floor()
            it = Vec2d(0, 0)
            for it.y in range(start.y, end.y):
                for it.x in range(start.x, end.x):
                    rel = self.relPt(it * Game.tile_size).floored()
                    tile = self.level.getTile(it)
                    if tile.id != 0:
                        self.level.getTile(it).image.blit(*rel)

            if self.grid_on:
                # draw grid
                grid_color = (255, 255, 255, 255)
                coords = []
                x_tile_count = int(self.window.width / tiles.width)
                y_tile_count = int(self.window.height / tiles.height)
                for x in range(x_tile_count):
                    draw_x = int((x*tiles.width - self.scroll.x % tiles.width) * self.zoom)
                    coords += [draw_x, 0, draw_x, self.window.height]
                for y in range(y_tile_count):
                    draw_y = int((y*tiles.height - self.scroll.y % tiles.height) * self.zoom)
                    coords += [0, draw_y, self.window.width, draw_y]
                pyglet.graphics.draw(int(len(coords)/2), pyglet.gl.GL_LINES, ('v2i', coords), ('c4B', grid_color * int(len(coords)/2)))

            # draw selected tile
            if self.selected_tile is not None:
                tiles.info[self.selected_tile].image.blit(0, self.window.height - tiles.height)

        elif self.mode == LevelEditor.Mode.CHOOSE_TILE:
            palette = self.getTilePalette()
            for pos, tile in palette:
                tile.image.blit(pos.x, pos.y)
        elif self.mode == LevelEditor.Mode.PLAYTEST:
            super(LevelEditor, self).on_draw()

    def getTilePalette(self):
        x = 0
        max_x = self.window.width - tiles.width
        y = self.window.height - tiles.height
        for tile in tiles.info.values():
            yield (Vec2d(x, y), tile)
            x += tiles.width
            if x >= max_x:
                x = 0
                y -= tiles.height

    def on_key_press(self, symbol, modifiers):
        if self.mode == LevelEditor.Mode.NORMAL:
            if symbol == pyglet.window.key.G:
                self.grid_on = not self.grid_on
            elif symbol == pyglet.window.key.LEFT:
                self.scroll.x -= 100
            elif symbol == pyglet.window.key.RIGHT:
                self.scroll.x += 100
            elif symbol == pyglet.window.key.UP:
                self.scroll.y += 100
            elif symbol == pyglet.window.key.DOWN:
                self.scroll.y -= 100
            elif symbol == pyglet.window.key.PLUS:
                self.zoom *= 1.1
            elif symbol == pyglet.window.key.MINUS:
                self.zoom *= 0.9
            elif symbol == pyglet.window.key._0:
                self.zoom = 1
            elif symbol == pyglet.window.key.SPACE:
                self.mode = LevelEditor.Mode.CHOOSE_TILE
            elif symbol == pyglet.window.key.S:
                if modifiers & pyglet.window.key.MOD_CTRL:
                    self.level.save(self.level_filename)
                else:
                    self.level.start = self.absPt(self.mouse_pos)
                    print("setting start to {0}".format(self.level.start))
            elif symbol == pyglet.window.key.F5:
                self.playTest()
        elif self.mode == LevelEditor.Mode.PLAYTEST:
            if symbol == pyglet.window.key.F5:
                # stop playtest
                self.clearLevel()
                self.level = Level.load(self.tmp_filename, self.batch, self.group_bg)

                os.remove(self.tmp_filename)
                self.tmp_filename = None
            else:
                super(LevelEditor, self).on_key_press(symbol, modifiers)

    def on_key_release(self, symbol, modifiers):
        if self.mode == LevelEditor.Mode.CHOOSE_TILE:
            if symbol == pyglet.window.key.SPACE:
                self.mode = LevelEditor.Mode.NORMAL
        elif self.mode == LevelEditor.Mode.PLAYTEST:
            super(LevelEditor, self).on_key_release(symbol, modifiers)

    def handle_mouse(self, pt):
        if self.mode == LevelEditor.Mode.NORMAL:
            tile_pos = self.absPt(pt) / Game.tile_size
            self.mouse_pos = pt
            if self.left_mouse_down:
                self.level.setTile(tile_pos, self.selected_tile)
            elif self.right_mouse_down:
                self.level.setTile(tile_pos, 0)

    def on_mouse_motion(self, x, y, dx, dy):
        self.handle_mouse(Vec2d(x, y))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.handle_mouse(Vec2d(x, y))

    def on_mouse_press(self, x, y, button, modifiers):
        if button & pyglet.window.mouse.LEFT:
            self.left_mouse_down = True

            if self.mode == LevelEditor.Mode.CHOOSE_TILE:
                palette = self.getTilePalette()
                for pos, tile in palette:
                    if x >= pos.x and x <= pos.x + tiles.width and y >= pos.y and y <= pos.y + tiles.height:
                        self.selected_tile = tile.id
                        print("Selected {0}".format(tile.name))
                        break
        elif button & pyglet.window.mouse.RIGHT:
            self.right_mouse_down = True
        self.handle_mouse(Vec2d(x, y))

    def on_mouse_release(self, x, y, button, modifiers):
        if button & pyglet.window.mouse.LEFT:
            self.left_mouse_down = False
        elif button & pyglet.window.mouse.RIGHT:
            self.right_mouse_down = False

    def playTest(self):
        # save to temporary file
        self.tmp_filename = tempfile.mktemp()
        self.level.save(self.tmp_filename)

        # reset state
        super(LevelEditor, self).clearLevel()
        self.level = Level.load(self.tmp_filename, self.batch, self.group_bg)
        self.level.toQuickLookup()

        # start game
        self.mode = LevelEditor.Mode.PLAYTEST
        self.start()

    def _createWindow(self):
        super(LevelEditor, self)._createWindow()
        self.window.set_handler('on_mouse_motion', self.on_mouse_motion)
        self.window.set_handler('on_mouse_press', self.on_mouse_press)
        self.window.set_handler('on_mouse_release', self.on_mouse_release)
        self.window.set_handler('on_mouse_drag', self.on_mouse_drag)


        self.level = Level.load(self.level_filename, self.batch, self.group_bg)
