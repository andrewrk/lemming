from __future__ import division, print_function, unicode_literals
range = xrange

import tiles
import data
from vec2d import Vec2d

import pyglet
import sys
import pickle

class Game:
    target_fps = 60
    tile_size = (tiles.width, tiles.height)

    class Mode:
        NORMAL = 0
        CHOOSE_TILE = 1

    def load_images(self):
        tileset = pyglet.image.load('tiles', file=data.load("tiles.bmp"))
        for tile in tiles.info.values():
            tile['image'] = tileset.get_region(tile['x']*tiles.width, tile['y']*tiles.height, tiles.width, tiles.height)

    def __init__(self):
        self.load_images()
        self.clear_level()

    def clear_level(self):
        self.level = {
            'start': {'x': 0, 'y': 0},
            'tiles': {}, # (x, y) to {'tile'}
        }
        self.grid_on = True
        self.scroll = Vec2d(0, 0)
        self.zoom = 1
        self.level_filename = None
        self.mode = Game.Mode.NORMAL

        self.left_mouse_down = False
        self.right_mouse_down = False
        self.selected_tile = tiles.info.iteritems().next()[0]

    def update(self, dt):
        pass

    def on_draw(self):
        self.window.clear()

        if self.mode == Game.Mode.NORMAL:
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

            # draw tiles
            start = self.abs_pt(Vec2d(0, 0)) / (tiles.width, tiles.height)
            end = self.abs_pt(Vec2d(self.window.width, self.window.height)) / Game.tile_size
            start.floor()
            end.floor()
            it = Vec2d(0, 0)
            for it.y in range(start.y, end.y):
                for it.x in range(start.x, end.x):
                    rel = self.rel_pt(it * Game.tile_size).floored()
                    tile = self.getTile(it)
                    if tile['id'] != 0:
                        self.getTile(it)['image'].blit(*rel)

            # draw selected tile
            if self.selected_tile is not None:
                tiles.info[self.selected_tile]['image'].blit(0, self.window.height - tiles.height)

        elif self.mode == Game.Mode.CHOOSE_TILE:
            palette = self.getTilePalette()
            for pos, tile in palette:
                tile['image'].blit(pos.x, pos.y)

    def getTile(self, pos):
        level_tiles = self.level['tiles']
        try:
            tile_id = level_tiles[tuple(pos.floored())]['tile']
        except KeyError:
            return tiles.info[0]
        return tiles.info[tile_id]

    def setTile(self, pos, tile_id):
        try:
            self.level['tiles'][tuple(pos.floored())]['tile'] = tile_id
        except KeyError:
            self.level['tiles'][tuple(pos.floored())] = {'tile': tile_id}

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
            self.mode = Game.Mode.CHOOSE_TILE

    def on_key_release(self, symbol, modifiers):
        if symbol == pyglet.window.key.SPACE:
            self.mode = Game.Mode.NORMAL
    def handle_mouse(self, pt):
        tile_pos = self.abs_pt(pt) / Game.tile_size
        if self.left_mouse_down:
            self.setTile(tile_pos, self.selected_tile)
        elif self.right_mouse_down:
            self.setTile(tile_pos, 0)

    def on_mouse_motion(self, x, y, dx, dy):
        self.handle_mouse(Vec2d(x, y))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.handle_mouse(Vec2d(x, y))

    def on_mouse_press(self, x, y, button, modifiers):
        if button & pyglet.window.mouse.LEFT:
            self.left_mouse_down = True

            if self.mode == Game.Mode.CHOOSE_TILE:
                palette = self.getTilePalette()
                for pos, tile in palette:
                    if x >= pos.x and x <= pos.x + tiles.width and y >= pos.y and y <= pos.y + tiles.height:
                        self.selected_tile = tile['id']
                        print("Selected {0}".format(tile['name']))
                        break
        elif button & pyglet.window.mouse.RIGHT:
            self.right_mouse_down = True
        self.handle_mouse(Vec2d(x, y))

    def on_mouse_release(self, x, y, button, modifiers):
        if button & pyglet.window.mouse.LEFT:
            self.left_mouse_down = False
        elif button & pyglet.window.mouse.RIGHT:
            self.right_mouse_down = False

    def abs_pt(self, rel_pt):
        return rel_pt / self.zoom + self.scroll

    def rel_pt(self, abs_pt):
        return (abs_pt - self.scroll) * self.zoom

    def load_level(self, filename):
        self.level_filename = filename

        pickle_error = False
        try:
            fd = open(filename, 'rb')
            self.level = pickle.load(fd)
            fd.close()
        except pickle.UnpicklingError:
            pickle_error = True
        except IOError:
            pickle_error = True
            
        if pickle_error:
            print("Error loading level")
            self.clear_level()
            return

    def saveLevel(self, filename):
        fd = open(filename, 'wb')
        pickle.dump(self.level, fd)
        fd.close()

    def start(self):
        self.window = pyglet.window.Window(width=1152, height=648, vsync=False)
        self.window.set_handler('on_draw', self.on_draw)
        self.window.set_handler('on_key_press', self.on_key_press)
        self.window.set_handler('on_key_release', self.on_key_release)
        self.window.set_handler('on_mouse_motion', self.on_mouse_motion)
        self.window.set_handler('on_mouse_press', self.on_mouse_press)
        self.window.set_handler('on_mouse_release', self.on_mouse_release)
        self.window.set_handler('on_mouse_drag', self.on_mouse_drag)
        pyglet.clock.schedule_interval(self.update, 1/Game.target_fps)

        self.parse_args()

        pyglet.app.run()
    def parse_args(self):
        from optparse import OptionParser
        parser = OptionParser("see --help for options")
        parser.add_option("-l", "--level", dest="level", help="level")

        options, args = parser.parse_args()
        options_dict = vars(options)
        
        if options_dict['level'] is not None:
            # load level from disk and go into level editor mode
            level_filename = options_dict['level']
            self.load_level(level_filename)
