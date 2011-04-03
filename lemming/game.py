from __future__ import division, print_function, unicode_literals
range = xrange

import pyglet
import tiles

import sys

target_fps = 60

class Game:
    def __init__(self):
        self.level = None
        self.grid_on = None
        self.scroll_x = None
        self.scroll_y = None
        self.zoom = None

    def clear_level(self):
        # level is a 2d grid of cells. [y][x]
        self.level = []
        self.grid_on = True
        self.scroll_x = 0
        self.scroll_y = 0
        self.zoom = 1

    def update(self, dt):
        pass

    def on_draw(self):
        self.window.clear()
        if self.grid_on:
            # draw grid
            grid_color = (255, 255, 255, 255)
            coords = []
            x_tile_count = int(self.window.width / tiles.width)
            y_tile_count = int(self.window.width / tiles.height)
            for x in range(x_tile_count):
                coords += [x*tiles.width, 0, x*tiles.width, self.window.height]
            for y in range(y_tile_count):
                coords += [0, y*tiles.height, self.window.width, y*tiles.height]
            pyglet.graphics.draw(int(len(coords)/2), pyglet.gl.GL_LINES, ('v2i', coords), ('c4B', grid_color * int(len(coords)/2)))

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.G:
            self.grid_on = not self.grid_on

    def on_mouse_motion(self, x, y, dx, dy):
        pass

    def on_mouse_press(self, x, y, button, modifiers):
        pass

    def on_mouse_release(self, x, y, button, modifiers):
        pass

    def abs_pt(self, rel_pt_x, rel_pt_y):
        return rel_pt_x * self.zoom + self.scroll_x, rel_pt_y * self.zoom + self.scroll_y

    def rel_pt(self, abs_pt_x, abs_pt_y):
        return (abs_pt_x - self.scroll_y) / self.zoom, (abs_pt_y - self.scroll_y) / self.zoom

    def load_level(self, level_data):
        pass

    def start(self):
        self.window = pyglet.window.Window()
        self.window.set_handler('on_draw', self.on_draw)
        self.window.set_handler('on_key_press', self.on_key_press)
        self.window.set_handler('on_mouse_motion', self.on_mouse_motion)
        self.window.set_handler('on_mouse_press', self.on_mouse_press)
        self.window.set_handler('on_mouse_release', self.on_mouse_release)
        pyglet.clock.schedule_interval(self.update, 1/target_fps)

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
            level_data = None
            try:
                f = open(level_filename, 'rb')
                level_data = f.read()
                f.close()
            except IOError:
                # new level
                pass
            if level_data is not None:
                self.load_level(level_data)
            else:
                self.clear_level()
