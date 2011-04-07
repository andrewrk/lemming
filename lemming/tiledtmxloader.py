#!/usr/bin/python


import sys
from xml.dom import minidom, Node
import StringIO
import pyglet

#-------------------------------------------------------------------------------
# TODO: separate resource loading and containment into own class for each graphics lib
#       by doing so, loading the map can be done in the model, loading the graphics resources in the presentation layer
class IImageLoader(object):
    u"""
    Interface for image loading. Depending on the framework used the
    images have to be loaded differently.
    """

    def load_image(self, filename, colorkey=None): # -> image
        u"""
        Load a single image.

        :Parameters:
            filename : string
                Path to the file to be loaded.
            colorkey : tuple
                The (r, g, b) color that should be used as colorkey (or magic color).
                Default: None

        :rtype: image

        """
        raise NotImplementedError(u'This should be implemented in a inherited class')

    def load_image_file_like(self, file_like_obj, colorkey=None): # -> image
        u"""
        Load a image from a file like object.

        :Parameters:
            file_like_obj : file
                This is the file like object to load the image from.
            colorkey : tuple
                The (r, g, b) color that should be used as colorkey (or magic color).
                Default: None

        :rtype: image
        """
        raise NotImplementedError(u'This should be implemented in a inherited class')

    def load_image_parts(self, filename, margin, spacing, tile_width, tile_height, colorkey=None): #-> [images]
        u"""
        Load different tile images from one source image.

        :Parameters:
            filename : string
                Path to image to be loaded.
            margin : int
                The margin around the image.
            spacing : int
                The space between the tile images.
            tile_width : int
                The width of a single tile.
            tile_height : int
                The height of a single tile.
            colorkey : tuple
                The (r, g, b) color that should be used as colorkey (or magic color).
                Default: None

        Luckily that iteration is so easy in python::

            ...
            w, h = image_size
            for y in xrange(margin, h, tile_height + spacing):
                for x in xrange(margin, w, tile_width + spacing):
                    ...

        :rtype: a list of images
        """
        raise NotImplementedError(u'This should be implemented in a inherited class')

#-------------------------------------------------------------------------------
#-------------------------------------------------------------------------------
class ImageLoaderPyglet(IImageLoader):
    u"""
    Pyglet image loader.

    It uses an internal image cache. The methods return some form of
    AbstractImage. The resource module is not used for loading the images.

    Thanks to HydroKirby from #pyglet to contribute the ImageLoaderPyglet and the pyglet demo!

    :Undocumented:
        pyglet
    """


    def __init__(self):
        self._img_cache = {} # {name: image}

    def load_image(self, filename, colorkey=None, fileobj=None):
        img = self._img_cache.get(filename, None)
        if img is None:
            if fileobj:
                img = pyglet.image.load(filename, fileobj, pyglet.image.codecs.get_decoders("*.png")[0])
            else:
                img = pyglet.resource.image(filename)
            self._img_cache[filename] = img
        return img

    def load_image_part(self, filename, x, y, w, h, colorkey=None):
        image = self.load_image(filename, colorkey)
        img_part = image.get_region(x, y, w, h)
        return img_part


    def load_image_parts(self, filename, margin, spacing, tile_width, tile_height, colorkey=None): #-> [images]
        source_img = self.load_image(filename, colorkey)
        images = []
        # Reverse the map column reading to compensate for pyglet's y-origin.
        for y in xrange(source_img.height - tile_height, margin - tile_height,
            -tile_height - spacing):
            for x in xrange(margin, source_img.width, tile_width + spacing):
                img_part = self.load_image_part(filename, x, y - spacing, tile_width, tile_height)
                images.append(img_part)
        return images

    def load_image_file_like(self, file_like_obj, colorkey=None): # -> image
        # pyglet.image.load can load from a path and from a file-like object
        # that is why here it is redirected to the other method
        return self.load_image(file_like_obj, colorkey, file_like_obj)

#-------------------------------------------------------------------------------
class TileMap(object):
    u"""

    The TileMap holds all the map data.

    :Ivariables:
        orientation : string
            orthogonal or isometric or hexagonal or shifted
        tilewidth : int
            width of the tiles (for all layers)
        tileheight : int
            height of the tiles (for all layers)
        width : int
            width of the map (number of tiles)
        height : int
            height of the map (number of tiles)
        version : string
            version of the map format
        tile_sets : list
            list of TileSet
        properties : dict
            the propertis set in the editor, name-value pairs, strings
        pixel_width : int
            width of the map in pixels
        pixel_height : int
            height of the map in pixels
        layers : list
            list of TileLayer
        object_groups : list
            list of :class:MapObjectGroup
        indexed_tiles : dict
            dict containing {gid : (offsetx, offsety, surface} if load() was called
            when drawing just add the offset values to the draw point
        named_layers : dict of string:TledLayer
            dict containing {name : TileLayer}
        named_tile_sets : dict
            dict containing {name : TileSet}

    """


    def __init__(self):
#        This is the top container for all data. The gid is the global id (for a image).
#        Before calling convert most of the values are strings. Some additional
#        values are also calculated, see convert() for details. After calling
#        convert, most values are integers or floats where appropriat.
        u"""
        The TileMap holds all the map data.
        """
        # set through parser
        self.orientation = None
        self.tileheight = 0
        self.tilewidth = 0
        self.width = 0
        self.height = 0
        self.version = 0
        self.tile_sets = [] # TileSet
        self.layers = [] # WorldTileLayer <- what order? back to front (guessed)
        self.indexed_tiles = {} # {gid: (offsetx, offsety, image}
        self.object_groups = []
        self.properties = {} # {name: value}
        # additional info
        self.pixel_width = 0
        self.pixel_height = 0
        self.named_layers = {} # {name: layer}
        self.named_tile_sets = {} # {name: tile_set}
        self._image_loader = None

    def convert(self):
        u"""
        Converts numerical values from strings to numerical values.
        It also calculates or set additional data:
        pixel_width
        pixel_height
        named_layers
        named_tile_sets
        """
        self.tilewidth = int(self.tilewidth)
        self.tileheight = int(self.tileheight)
        self.width = int(self.width)
        self.height = int(self.height)
        self.pixel_width = self.width * self.tilewidth
        self.pixel_height = self.height * self.tileheight
        for layer in self.layers:
            self.named_layers[layer.name] = layer
            layer.opacity = float(layer.opacity)
            layer.x = int(layer.x)
            layer.y = int(layer.y)
            layer.width = int(layer.width)
            layer.height = int(layer.height)
            layer.pixel_width = layer.width * self.tilewidth
            layer.pixel_height = layer.height * self.tileheight
            layer.visible = bool(int(layer.visible))
        for tile_set in self.tile_sets:
            self.named_tile_sets[tile_set.name] = tile_set
            tile_set.spacing = int(tile_set.spacing)
            tile_set.margin = int(tile_set.margin)
            for img in tile_set.images:
                if img.trans:
                    img.trans = (int(img.trans[:2], 16), int(img.trans[2:4], 16), int(img.trans[4:], 16))
        for obj_group in self.object_groups:
            obj_group.x = int(obj_group.x)
            obj_group.y = int(obj_group.y)
            obj_group.width = int(obj_group.width)
            obj_group.height = int(obj_group.height)
            for map_obj in obj_group.objects:
                map_obj.x = int(map_obj.x)
                map_obj.y = int(map_obj.y)
                map_obj.width = int(map_obj.width)
                map_obj.height = int(map_obj.height)

    def load(self, image_loader):
        u"""
        loads all images using a IImageLoadermage implementation and fills up
        the indexed_tiles dictionary.
        The image may have per pixel alpha or a colorkey set.
        """
        self._image_loader = image_loader
        for tile_set in self.tile_sets:
            # do images first, because tiles could reference it
            for img in tile_set.images:
                if img.source:
                    self._load_image_from_source(tile_set, img)
                else:
                    tile_set.indexed_images[img.id] = self._load_image(img)
            # tiles
            for tile in tile_set.tiles:
                for img in tile.images:
                    if not img.content and not img.source:
                        # only image id set
                        indexed_img = tile_set.indexed_images[img.id]
                        self.indexed_tiles[int(tile_set.firstgid) + int(tile.id)] = (0, 0, indexed_img)
                    else:
                        if img.source:
                            self._load_image_from_source(tile_set, img)
                        else:
                            indexed_img = self._load_image(img)
                            self.indexed_tiles[int(tile_set.firstgid) + int(tile.id)] = (0, 0, indexed_img)

    def _load_image_from_source(self, tile_set, a_tile_image):
        # relative path to file
        img_path = a_tile_image.source
        tile_width = int(self.tilewidth)
        tile_height = int(self.tileheight)
        if tile_set.tileheight:
            tile_width = int(tile_set.tilewidth)
        if tile_set.tilewidth:
            tile_height = int(tile_set.tileheight)
        offsetx = 0
        offsety = 0
        if tile_height > self.tileheight:
            offsety = tile_height - self.tileheight
        idx = 0
        for image in self._image_loader.load_image_parts(img_path, \
                    tile_set.margin, tile_set.spacing, tile_width, tile_height, a_tile_image.trans):
            self.indexed_tiles[int(tile_set.firstgid) + idx] = (offsetx, -offsety, image)
            idx += 1

    def _load_image(self, a_tile_image):
        img_str = a_tile_image.content
        if a_tile_image.encoding:
            if a_tile_image.encoding == u'base64':
                img_str = decode_base64(a_tile_image.content)
            else:
                raise Exception(u'unknown image encoding %s' % a_tile_image.encoding)
        sio = StringIO.StringIO(img_str)
        new_image = self._image_loader.load_image_file_like(sio, a_tile_image.trans)
        return new_image

    def decode(self):
        u"""
        Decodes the TileLayer encoded_content and saves it in decoded_content.
        """
        for layer in self.layers:
            layer.decode()
#-------------------------------------------------------------------------------


class TileSet(object):
    u"""
    A tileset holds the tiles and its images.

    :Ivariables:
        firstgid : int
            the first gid of this tileset
        name : string
            the name of this TileSet
        images : list
            list of TileImages
        tiles : list
            list of Tiles
        indexed_images : dict
            after calling load() it is dict containing id: image
        indexed_tiles : dict
            after calling load() it is a dict containing
            gid: (offsetx, offsety, image) , the image corresponding to the gid
        spacing : int
            the spacing between tiles
        marging : int
            the marging of the tiles
        properties : dict
            the propertis set in the editor, name-value pairs
        tilewidth : int
            the actual width of the tile, can be different from the tilewidth of the map
        tilehight : int
            the actual hight of th etile, can be different from the tilehight of the  map

    """

    def __init__(self):
        self.firstgid = 0
        self.name = None
        self.images = [] # TileImage
        self.tiles = [] # Tile
        self.indexed_images = {} # {id:image}
        self.indexed_tiles = {} # {gid: (offsetx, offsety, image} <- actually in map data
        self.spacing = 0
        self.margin = 0
        self.properties = {}
        self.tileheight = 0
        self.tilewidth = 0

#-------------------------------------------------------------------------------

class TileImage(object):
    u"""
    An image of a tile or just an image.

    :Ivariables:
        id : int
            id of this image (has nothing to do with gid)
        format : string
            the format as string, only 'png' at the moment
        source : string
            filename of the image. either this is set or the content
        encoding : string
            encoding of the content
        trans : tuple of (r,g,b)
            the colorkey color, raw as hex, after calling convert just a (r,g,b) tuple
        properties : dict
            the propertis set in the editor, name-value pairs
        image : TileImage
            after calling load the pygame surface
    """

    def __init__(self):
        self.id = 0
        self.format = None
        self.source = None
        self.encoding = None # from <data>...</data>
        self.content = None # from <data>...</data>
        self.image = None
        self.trans = None
        self.properties = {} # {name: value}

#-------------------------------------------------------------------------------

class Tile(object):
    u"""
    A single tile.

    :Ivariables:
        id : int
            id of the tile gid = TileSet.firstgid + Tile.id
        images : list of :class:TileImage
            list of TileImage, either its 'id' or 'image data' will be set
        properties : dict of name:value
            the propertis set in the editor, name-value pairs
    """

    def __init__(self):
        self.id = 0
        self.images = [] # uses TileImage but either only id will be set or image data
        self.properties = {} # {name: value}

#-------------------------------------------------------------------------------

class TileLayer(object):
    u"""
    A layer of the world.

    :Ivariables:
        x : int
            position of layer in the world in number of tiles (not pixels)
        y : int
            position of layer in the world in number of tiles (not pixels)
        width : int
            number of tiles in x direction
        height : int
            number of tiles in y direction
        pixel_width : int
            width of layer in pixels
        pixel_height : int
            height of layer in pixels
        name : string
            name of this layer
        opacity : float
            float from 0 (full transparent) to 1.0 (opaque)
        decoded_content : list
            list of graphics id going through the map::

                e.g [1, 1, 1, ]
                where decoded_content[0] is (0,0)
                      decoded_content[1] is (1,0)
                      ...
                      decoded_content[1] is (width,0)
                      decoded_content[1] is (0,1)
                      ...
                      decoded_content[1] is (width,height)

                usage: graphics id = decoded_content[tile_x + tile_y * width]
        content2D : list
            list of list, usage: graphics id = content2D[x][y]

    """

    def __init__(self):
        self.width = 0
        self.height = 0
        self.x = 0
        self.y = 0
        self.pixel_width = 0
        self.pixel_height = 0
        self.name = None
        self.opacity = -1
        self.encoding = None
        self.compression = None
        self.encoded_content = None
        self.decoded_content = []
        self.visible = True
        self.properties = {} # {name: value}
        self.content2D = None

    def decode(self):
        u"""
        Converts the contents in a list of integers which are the gid of the used
        tiles. If necessairy it decodes and uncompresses the contents.
        """
        self.decoded_content = []
        if self.encoded_content:
            s = self.encoded_content
            if self.encoding:
                if self.encoding.lower() == u'base64':
                    s = decode_base64(s)
                elif self.encoding.lower() == u'csv':
                    list_of_lines = s.split()
                    for line in list_of_lines:
                        self.decoded_content.extend(line.split(','))
                    self.decoded_content = map(int, [val for val in self.decoded_content if val])
                    s = ""
                else:
                    raise Exception(u'unknown data encoding %s' % (self.encoding))
            else:
                # in the case of xml the encoded_content already contains a list of integers
                self.decoded_content = map(int, self.encoded_content)
                s = ""
            if self.compression:
                if self.compression == u'gzip':
                    s = decompress_gzip(s)
                elif self.compression == u'zlib':
                    s = decompress_zlib(s)
                else:
                    raise Exception(u'unknown data compression %s' %(self.compression))
        else:
            raise Exception(u'no encoded content to decode')
        for idx in xrange(0, len(s), 4):
            val = ord(str(s[idx])) | (ord(str(s[idx + 1])) << 8) | \
                 (ord(str(s[idx + 2])) << 16) | (ord(str(s[idx + 3])) << 24)
            self.decoded_content.append(val)
        # generate the 2D version
        self._gen_2D()

    def _gen_2D(self):
        self.content2D = []
        # generate the needed lists
        for xpos in xrange(self.width):
            self.content2D.append([])
        # fill them
        for xpos in xrange(self.width):
            for ypos in xrange(self.height):
                self.content2D[xpos].append(self.decoded_content[xpos + ypos * self.width])

#-------------------------------------------------------------------------------


class MapObjectGroup(object):
    u"""
    Group of objects on the map.

    :Ivariables:
        x : int
            the x position
        y : int
            the y position
        width : int
            width of the bounding box (usually 0, so no use)
        height : int
            height of the bounding box (usually 0, so no use)
        name : string
            name of the group
        objects : list
            list of the map objects

    """

    def __init__(self):
        self.width = 0
        self.height = 0
        self.name = None
        self.objects = []
        self.x = 0
        self.y = 0
        self.properties = {} # {name: value}

#-------------------------------------------------------------------------------

class MapObject(object):
    u"""
    A single object on the map.

    :Ivariables:
        x : int
            x position relative to group x position
        y : int
            y position relative to group y position
        width : int
            width of this object
        height : int
            height of this object
        type : string
            the type of this object
        image_source : string
            source path of the image for this object
        image : :class:TileImage
            after loading this is the pygame surface containing the image
    """
    def __init__(self):
        self.name = None
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0
        self.type = None
        self.image_source = None
        self.image = None
        self.properties = {} # {name: value}

#-------------------------------------------------------------------------------
def decode_base64(in_str):
    u"""
    Decodes a base64 string and returns it.

    :Parameters:
        in_str : string
            base64 encoded string

    :returns: decoded string
    """
    import base64
    return base64.decodestring(in_str)

#-------------------------------------------------------------------------------
def decompress_gzip(in_str):
    u"""
    Uncompresses a gzip string and returns it.

    :Parameters:
        in_str : string
            gzip compressed string

    :returns: uncompressed string
    """
    import gzip
    # gzip can only handle file object therefore using StringIO
    copmressed_stream = StringIO.StringIO(in_str)
    gzipper = gzip.GzipFile(fileobj=copmressed_stream)
    s = gzipper.read()
    gzipper.close()
    return s

#-------------------------------------------------------------------------------
def decompress_zlib(in_str):
    u"""
    Uncompresses a zlib string and returns it.

    :Parameters:
        in_str : string
            zlib compressed string

    :returns: uncompressed string
    """
    import zlib
    s = zlib.decompress(in_str)
    return s
#-------------------------------------------------------------------------------
class TileMapParser(object):
    u"""
    Allows to parse and decode map files for 'Tiled', a open source map editor
    written in java. It can be found here: http://mapeditor.org/
    """

    def _build_tile_set(self, tile_set_node, world_map):
        tile_set = TileSet()
        self._set_attributes(tile_set_node, tile_set)
        if hasattr(tile_set, "source"):
            tile_set = self._parse_tsx(tile_set.source, tile_set, world_map)
        else:
            tile_set = self._get_tile_set(tile_set_node, tile_set, self.map_file_name)
        world_map.tile_sets.append(tile_set)

    def _parse_tsx(self, file_name, tile_set, world_map):
        file = None
        try:
            file = pyglet.resource.file(file_name)
            dom = minidom.parseString(file.read())
        finally:
            if file:
                file.close()
        for node in self._get_nodes(dom.childNodes, 'tileset'):
            tile_set = self._get_tile_set(node, tile_set, file_name)
            break;
        return tile_set

    def _get_tile_set(self, tile_set_node, tile_set, base_path):
        for node in self._get_nodes(tile_set_node.childNodes, u'image'):
            self._build_tile_set_image(node, tile_set, base_path)
        for node in self._get_nodes(tile_set_node.childNodes, u'tile'):
            self._build_tile_set_tile(node, tile_set)
        self._set_attributes(tile_set_node, tile_set)
        return tile_set

    def _build_tile_set_image(self, image_node, tile_set, base_path):
        image = TileImage()
        self._set_attributes(image_node, image)
        # id of TileImage has to be set!! -> Tile.TileImage will only have id set
        for node in self._get_nodes(image_node.childNodes, u'data'):
            self._set_attributes(node, image)
            image.content = node.childNodes[0].nodeValue
        tile_set.images.append(image)

    def _build_tile_set_tile(self, tile_set_node, tile_set):
        tile = Tile()
        self._set_attributes(tile_set_node, tile)
        for node in self._get_nodes(tile_set_node.childNodes, u'image'):
            self._build_tile_set_tile_image(node, tile)
        tile_set.tiles.append(tile)

    def _build_tile_set_tile_image(self, tile_node, tile):
        tile_image = TileImage()
        self._set_attributes(tile_node, tile_image)
        for node in self._get_nodes(tile_node.childNodes, u'data'):
            self._set_attributes(node, tile_image)
            tile_image.content = node.childNodes[0].nodeValue
        tile.images.append(tile_image)

    def _build_layer(self, layer_node, world_map):
        layer = TileLayer()
        self._set_attributes(layer_node, layer)
        for node in self._get_nodes(layer_node.childNodes, u'data'):
            self._set_attributes(node, layer)
            if layer.encoding:
                layer.encoded_content = node.lastChild.nodeValue
            else:
                layer.encoded_content = []
                for child in node.childNodes:
                    if child.nodeType == Node.ELEMENT_NODE and child.nodeName == "tile":
                        val = child.attributes["gid"].nodeValue
                        layer.encoded_content.append(val)
        world_map.layers.append(layer)

    def _build_world_map(self, world_node):
        world_map = TileMap()
        self._set_attributes(world_node, world_map)
        if world_map.version != u"1.0":
            raise Exception(u'this parser was made for maps of version 1.0, found version %s' % world_map.version)
        for node in self._get_nodes(world_node.childNodes, u'tileset'):
            self._build_tile_set(node, world_map)
        for node in self._get_nodes(world_node.childNodes, u'layer'):
            self._build_layer(node, world_map)
        for node in self._get_nodes(world_node.childNodes, u'objectgroup'):
            self._build_object_groups(node, world_map)
        return world_map

    def _build_object_groups(self, object_group_node, world_map):
        object_group = MapObjectGroup()
        self._set_attributes(object_group_node,  object_group)
        for node in self._get_nodes(object_group_node.childNodes, u'object'):
            tiled_object = MapObject()
            self._set_attributes(node, tiled_object)
            for img_node in self._get_nodes(node.childNodes, u'image'):
                tiled_object.image_source = img_node.attributes[u'source'].nodeValue
            object_group.objects.append(tiled_object)
        world_map.object_groups.append(object_group)

    #-- helpers --#
    def _get_nodes(self, nodes, name):
        for node in nodes:
            if node.nodeType == Node.ELEMENT_NODE and node.nodeName == name:
                yield node

    def _set_attributes(self, node, obj):
        attrs = node.attributes
        for attr_name in attrs.keys():
            setattr(obj, attr_name, attrs.get(attr_name).nodeValue)
        self._get_properties(node, obj)


    def _get_properties(self, node, obj):
        props = {}
        for properties_node in self._get_nodes(node.childNodes, u'properties'):
            for property_node in self._get_nodes(properties_node.childNodes, u'property'):
                try:
                    props[property_node.attributes[u'name'].nodeValue] = property_node.attributes[u'value'].nodeValue
                except KeyError:
                    props[property_node.attributes[u'name'].nodeValue] = property_node.lastChild.nodeValue
        obj.properties.update(props)


    #-- parsers --#
    def parse(self, open_file):
        u"""
        Parses the given map. Does no decoding nor loading the data.
        :return: instance of TileMap
        """
        try:
            dom = minidom.parseString(open_file.read())
        finally:
            open_file.close()
        for node in self._get_nodes(dom.childNodes, 'map'):
            world_map = self._build_world_map(node)
            break
        world_map.convert()
        return world_map

    def parse_decode(self, open_file):
        u"""
        Parses the map but additionally decodes the data.
        :return: instance of TileMap
        """
        world_map = TileMapParser().parse(open_file)
        world_map.decode()
        return world_map

    def parse_decode_load(self, open_file, image_loader):
        u"""
        Parses the data, decodes them and loads the images using the image_loader.
        :return: instance of TileMap
        """
        world_map = self.parse_decode(open_file)
        world_map.load(image_loader)
        return world_map

