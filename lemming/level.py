from __future__ import division, print_function, unicode_literals
range = xrange

import pyglet
import tiles
from vec2d import Vec2d

class Square(object):
    def __init__(self, sprite=None, tile=0, batch=None, group=None):
        self.tile = tile
        self.sprite = sprite

        if self.sprite is None and self.tile != 0:
            self.sprite = pyglet.sprite.Sprite(tiles.info[self.tile].image, batch=batch, group=group)

class Level(object):
    def __init__(self, batch=None, group=None):
        self.start = Vec2d(0, 0)
        self.squares = {}
        self.sparse = True
        self.batch = batch
        self.group = group

    def getSquare(self, pos):
        floored_pos = pos.floored()
        if self.sparse:
            try:
                return self.squares[tuple(floored_pos)]
            except KeyError:
                return None
        else:
            index = self.getIndex(*floored_pos)
            if index >= 0 and index < len(self.squares):
                return self.squares[index]
            else:
                return None

    def getTile(self, pos):
        floored_pos = pos.floored()
        if self.sparse:
            try:
                tile_id = self.squares[tuple(floored_pos)].tile
            except KeyError:
                return tiles.info[0]
            return tiles.info[tile_id]
        else:
            index = self.getIndex(*floored_pos)
            if index >= 0 and index < len(self.squares):
                return tiles.info[self.squares[index].tile]
            else:
                return tiles.info[0]

    def setTile(self, pos, tile_id):
        assert self.sparse
        floored_pos = pos.floored()
        try:
            self.squares[tuple(floored_pos)] = Square(tile=tile_id, batch=self.batch, group=self.group)
        except KeyError:
            self.squares[tuple(floored_pos)] = Square()

    def getIndex(self, x, y):
        return y*self.width + x

    def toQuickLookup(self):
        assert self.sparse
        # convert the sparse array to a quick lookup
        min_pos = Vec2d(self.squares.iteritems().next()[0])
        max_pos = Vec2d(min_pos)
        for x,y in self.squares.keys():
            if x < min_pos.x:
                min_pos.x = x
            if y < min_pos.y:
                min_pos.y = y
            if x > max_pos.x:
                max_pos.x = x
            if y > max_pos.y:
                max_pos.y = y
        
        self.width = (max_pos.x - min_pos.x) + 1
        self.height = (max_pos.y - min_pos.y) + 1

        new_squares = [Square()] * (self.width*self.height)

        self.start -= min_pos * (tiles.width, tiles.height)

        self.sparse = False
        for (x, y), sq in self.squares.iteritems():
            new_squares[self.getIndex(x-min_pos.x,y-min_pos.y)] = sq
        self.squares = new_squares


    @staticmethod
    def load(filename, batch, group):
        try:
            fd = open(filename, 'rb')
        except IOError:
            print("Error loading level")
            return Level(batch, group)
        data = fd.read()
        fd.close()

        lvl = Level(batch, group)

        lines = data.split('\n')
        lvl.start = Vec2d(map(float, lines[0].split(',')))

        sq_count = int(lines[1])
        line_index = 2
        for i in range(sq_count):
            x, y, tile_id = map(int, lines[line_index].split(','))
            line_index += 1

            lvl.squares[(x, y)] = Square(tile=tile_id, batch=batch, group=group)

        return lvl


    def save(self, filename):
        assert self.sparse

        print("saving to {0}".format(filename))
        fd = open(filename, 'wb')

        fd.write("{0}, {1}\n".format(*self.start))
        fd.write("{0}\n".format(len(self.squares)))
        for (x, y), sq in self.squares.iteritems():
            fd.write("{0}, {1}, {2}\n".format(x, y, sq.tile))
        
        fd.close()
