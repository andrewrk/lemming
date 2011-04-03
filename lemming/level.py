from __future__ import division, print_function, unicode_literals
range = xrange

import tiles
import pickle
from vec2d import Vec2d

class Square(object):
    def __init__(self, tile=0):
        self.tile = tile

class Level(object):
    def __init__(self):
        self.start = Vec2d(0, 0)
        self.tile_count_x = 0
        self.tile_count_y = 0
        self.squares = {}

    def getTile(self, pos):
        try:
            tile_id = self.squares[tuple(pos.floored())].tile
        except KeyError:
            return tiles.info[0]
        return tiles.info[tile_id]

    def setTile(self, pos, tile_id):
        try:
            self.squares[tuple(pos.floored())].tile = tile_id
        except KeyError:
            self.squares[tuple(pos.floored())] = Square(tile_id)

    @staticmethod
    def load(filename):
        pickle_error = False
        try:
            fd = open(filename, 'rb')
            obj = pickle.load(fd)
            fd.close()
            return obj
        except pickle.UnpicklingError:
            pickle_error = True
        except IOError:
            pickle_error = True
        except EOFError:
            pickle_error = True
            
        if pickle_error:
            print("Error loading level")
            return Level()

    def save(self, filename):
        print("saving to {0}".format(filename))
        fd = open(filename, 'wb')
        pickle.dump(self, fd)
        fd.close()
