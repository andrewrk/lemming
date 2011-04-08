from __future__ import division, print_function, unicode_literals
range = xrange

import tiledtmxloader

class loose_obj(object):
    def __init__(self, d=None):
        if d is None:
            d = {}
        self._attrs = d

    def __getattr__(self, name):
        try:
            return self._attrs[name]
        except KeyError:
            return None

class strict_obj(object):
    def __init__(self, d=None):
        if d is None:
            d = {}
        self._attrs = d

    def __getattr__(self, name):
        return self._attrs[name]


class TileSet(object):
    def __init__(self, tsx_tileset):
        self.info = {}

        _bool = lambda b: bool(int(b))
        property_types = {
            # unspecified is str
            'solid': _bool,
            'spike': _bool,
            'mine': _bool,
            'ramp': int,
            'belt': int,
        }
        _enum = {}
        self.info[0] = loose_obj({'id': 0, 'name': 'Air'})
        _enum['Air'] = 0
        for tile in tsx_tileset.tiles:
            tile.id = int(tile.id) + 1
            props = {}
            props['id'] = tile.id
            for name, value in tile.properties.iteritems():
                try:
                    value = property_types[name](value)
                except KeyError:
                    pass
                props[name] = value

                #print("{0} - {1}: {2}".format(id, name, value))
            
            self.info[tile.id] = loose_obj(props)
            _enum[self.info[tile.id].name] = tile.id

        self.enum = strict_obj(_enum)
