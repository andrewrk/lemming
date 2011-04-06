from __future__ import division, print_function, unicode_literals
range = xrange

from tiles import TileSet
from vec2d import Vec2d
import tiledtmxloader

import pyglet
import sys
import itertools
import math

import os

# add data folder to pyglet resource path
_this_py = os.path.abspath(os.path.dirname(__file__))
_data_dir = os.path.normpath(os.path.join(_this_py, '..', 'data'))
pyglet.resource.path = [_data_dir]
pyglet.resource.reindex()

# monkey patch pyglet to fix a resource loading bug
slash_paths = filter(lambda x: x.startswith('/'), pyglet.resource._default_loader._index.keys())
for path in slash_paths:
    pyglet.resource._default_loader._index[path[1:]] = pyglet.resource._default_loader._index[path]

def sign(n):
    if n > 0:
        return 1
    elif n < 0:
        return -1
    else:
        return 0

def abs_min(a, b):
    if abs(a) < abs(b):
        return a
    return b

class Game(object):
    class Control:
        MoveLeft = 0
        MoveRight = 1
        Jump = 2
        BellyFlop = 3
        Freeze = 4
        Explode = 5

    class LemmingFrame(object):
        def __init__(self, pos, vel, next_node, new_image=None):
            self.pos = pos
            self.vel = vel
            self.next_node = next_node
            self.prev_node = None
            self.new_image = new_image
            
            if self.next_node is not None:
                self.next_node.prev_node = self

    class PhysicsObject(object):
        def __init__(self, pos, vel, sprite, size, life=None, can_pick_up_stuff=False, is_belly_flop=False, direction=1):
            self.pos = pos
            self.vel = vel
            self.sprite = sprite
            self.size = size # in tiles
            self.life = life
            self.gone = False
            self.can_pick_up_stuff = can_pick_up_stuff
            self.is_belly_flop = is_belly_flop
            self.direction = direction

    class Lemming(PhysicsObject):
        def __init__(self, sprite, frame=None):
            if frame is not None:
                super(Game.Lemming, self).__init__(frame.pos, frame.vel, sprite, Vec2d(1, 4), can_pick_up_stuff=True)
            else:
                super(Game.Lemming, self).__init__(None, None, sprite, Vec2d(1, 4), can_pick_up_stuff=True)
            self.frame = frame
            self.gone = False

    target_fps = 60
    tile_size = None
    lemming_count = 9
    lemming_response_time = 0.40

    def getNextGroupNum(self):
        val = self.next_group_num
        self.next_group_num += 1
        return val

    def loadImages(self):
        # load animations
        fd = pyglet.resource.file('animations.txt')
        animations_txt = fd.read()
        fd.close()
        lines = animations_txt.split('\n')
        self.animations = {}
        self.animation_offset = {}
        for full_line in lines:
            line = full_line.strip()
            if line.startswith('#') or len(line) == 0:
                continue
            props, frames_txt = line.split('=')

            name, delay, loop, off_x, off_y = props.strip().split(':')
            delay = float(delay.strip())
            loop = bool(int(loop.strip()))

            frame_files = frames_txt.strip().split(',')
            frame_list = [pyglet.image.AnimationFrame(pyglet.resource.image(x.strip()), delay) for x in frame_files]
            rev_frame_list = [pyglet.image.AnimationFrame(pyglet.resource.image(x.strip(), flip_x=True), delay) for x in frame_files]
            if not loop:
                frame_list[-1].duration = None
                rev_frame_list[-1].duration = None

            animation = pyglet.image.Animation(frame_list)
            rev_animation = pyglet.image.Animation(rev_frame_list)
            self.animations[name.strip()] = animation
            self.animations['-' + name.strip()] = rev_animation

            self.animation_offset[animation] = Vec2d(-int(off_x), -int(off_y))
            self.animation_offset[rev_animation] = Vec2d(int(off_x)+self.level.tilewidth, -int(off_y))

        self.img_bg = pyglet.resource.image("background.png")
        self.img_bg_hill = pyglet.resource.image("hill.png")

        self.sprite_bg_left = pyglet.sprite.Sprite(self.img_bg, batch=self.batch_bg2)
        self.sprite_bg_right = pyglet.sprite.Sprite(self.img_bg, batch=self.batch_bg2)

        self.sprite_hill_left = pyglet.sprite.Sprite(self.img_bg_hill, batch=self.batch_bg1)
        self.sprite_hill_right = pyglet.sprite.Sprite(self.img_bg_hill, batch=self.batch_bg1)

        self.sprite_bg_left.set_position(0, 0)
        self.sprite_bg_right.set_position(self.sprite_bg_left.width, 0)

        self.sprite_hill_left.set_position(0, 0)
        self.sprite_hill_right.set_position(self.sprite_hill_left.width, 0)

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
        self.level = None

        self.batch_bg2 = pyglet.graphics.Batch()
        self.batch_bg1 = pyglet.graphics.Batch()
        self.batch_level = pyglet.graphics.Batch()

        self.loadConfig()

    def getDesiredScroll(self, point):
        scroll = Vec2d(point) - Vec2d(self.window.width, self.window.height) / 2
        if scroll.x < 0:
            scroll.x = 0
        if scroll.y < 0:
            scroll.y = 0
        if scroll.x > self.level.width * self.level.tilewidth - self.window.width:
            scroll.x = self.level.width * self.level.tilewidth  - self.window.width
        if scroll.y > self.level.height * self.level.tileheight - self.window.height:
            scroll.y = self.level.height * self.level.tileheight  - self.window.height
        return scroll

    def start(self):
        self.scroll = self.getDesiredScroll(self.start_point)
        self.scroll_vel = Vec2d(0, 0)
        self.last_scroll_delta = Vec2d(0, 0)
        self.lemmings = [None] * Game.lemming_count
        self.control_state = [False] * (len(dir(Game.Control)) - 2)
        self.physical_objects = []
        self.control_lemming = 0

        self.explode_queued = False # true when the user presses the button until an update happens
        self.bellyflop_queued = False
        self.freeze_queued = False
        self.plus_ones_queued = 0
        self.spike_death_queued = False

        # resets variables based on level and begins the game
        # generate data for each lemming
        for i in range(len(self.lemmings)):
            sprite = pyglet.sprite.Sprite(self.animations['lem_crazy'], batch=self.batch_level, group=self.group_char)
            if i > 0:
                sprite.opacity = 128
            self.lemmings[i] = Game.Lemming(sprite, None)

        # generate frames for trails
        head_frame = Game.LemmingFrame(Vec2d(self.start_point), Vec2d(0, 0), None)
        lemming_index = len(self.lemmings) - 1
        self.lemmings[lemming_index].frame = head_frame
        lemming_index -= 1
        lemming_frame_count = 1
        while Game.target_fps * Game.lemming_response_time * (len(self.lemmings)-1) > lemming_frame_count:
            head_frame = Game.LemmingFrame(Vec2d(head_frame.pos), Vec2d(head_frame.vel), head_frame)
            lemming_frame_count += 1
            if int((len(self.lemmings) - 1 - lemming_index) * Game.target_fps * Game.lemming_response_time) == lemming_frame_count:
                self.lemmings[lemming_index].frame = head_frame
                lemming_index -= 1

        pyglet.clock.schedule_interval(self.update, 1/Game.target_fps)
        pyglet.clock.schedule_interval(self.garbage_collect, 10)
        self.fps_display = pyglet.clock.ClockDisplay()


    def detatchHeadLemming(self):
        head_lemming = self.lemmings[self.control_lemming]

        head_lemming.sprite.delete()
        head_lemming.sprite = None

        self.control_lemming += 1
        head_lemming = self.lemmings[self.control_lemming]

        head_lemming.sprite.opacity = 255
        head_lemming.frame.prev_node = None

    def update(self, dt):
        if self.explode_queued:
            self.explode_queued = False

            old_head_lemming = self.lemmings[self.control_lemming]
            self.physical_objects.append(Game.PhysicsObject(old_head_lemming.frame.pos,
                old_head_lemming.frame.vel, pyglet.sprite.Sprite(self.animations['explosion'], batch=self.batch_level, group=self.group_fg),
                Vec2d(1, 1), self.animations['explosion'].get_duration()))

            self.detatchHeadLemming()
        elif self.spike_death_queued:
            self.spike_death_queued = False
            self.detatchHeadLemming()
        elif self.bellyflop_queued:
            self.bellyflop_queued = False

            old_head_lemming = self.lemmings[self.control_lemming]
            direction = sign(old_head_lemming.frame.vel.x)
            if direction < 0:
                animation = self.animations['-lem_belly_flop']
            else:
                direction = 1
                animation = self.animations['lem_belly_flop']
            self.physical_objects.append(Game.PhysicsObject(old_head_lemming.frame.pos,
                old_head_lemming.frame.vel, pyglet.sprite.Sprite(animation, batch=self.batch_level, group=self.group_fg),
                Vec2d(4, 1), can_pick_up_stuff=True, is_belly_flop=True, direction=direction))

            self.detatchHeadLemming()

        # add more lemmings
        while self.plus_ones_queued > 0 and self.control_lemming > 0:
            self.plus_ones_queued -= 1
            self.control_lemming -= 1
            for i in range(self.control_lemming, len(self.lemmings)-1):
                self.lemmings[i] = self.lemmings[i+1]
            # add the missing frames
            old_last_frame = self.lemmings[-2].frame
            last_lem = Game.Lemming(pyglet.sprite.Sprite(self.animations['lem_crazy'], batch=self.batch_level, group=self.group_char),
                Game.LemmingFrame(Vec2d(old_last_frame.pos), Vec2d(old_last_frame.vel), None))
            self.lemmings[-1] = last_lem
            last_lem.sprite.opacity = 128
            node = last_lem.frame
            for i in range(int(Game.target_fps * Game.lemming_response_time)):
                node = Game.LemmingFrame(Vec2d(old_last_frame.pos), Vec2d(old_last_frame.vel), node)
            old_last_frame.next_node = node
            node.prev_node = old_last_frame

        # lemming trails
        char = self.lemmings[self.control_lemming]
        char.frame = Game.LemmingFrame(Vec2d(char.frame.pos), Vec2d(char.frame.vel), char.frame)

        for lemming in self.lemmings[self.control_lemming+1:]:
            lemming.frame = lemming.frame.prev_node
        self.lemmings[-1].frame.next_node = None

        # physics
        char.pos = char.frame.pos
        char.vel = char.frame.vel
        for obj in itertools.chain(self.physical_objects, [char]):
            if obj.gone:
                continue

            if obj.life is not None:
                obj.life -= dt
                if obj.life <= 0:
                    obj.gone = True
                    obj.sprite.visible = False
                    continue

            # collision with solid blocks
            new_pos = obj.pos + obj.vel * dt
            def resolve_y(new_pos, vel, obj_size):
                new_feet_block = (new_pos / Game.tile_size).do(int)
                tile_there = self.getTile(new_feet_block)

                for x in range(obj_size.x):
                    # ramps
                    if tile_there.ramp == -1:
                        new_pos.y = new_feet_block.y * self.level.tileheight + self.level.tileheight
                        vel.y = 0
                        return
                    elif self.getTile(Vec2d(new_feet_block.x+1, new_feet_block.y)).ramp == 1:
                        new_pos.y = new_feet_block.y * self.level.tileheight + self.level.tileheight
                        vel.y = 0
                        return

                    if vel.y != 0:
                        # resolve feet collisions
                        if tile_there.solid:
                            new_pos.y = (new_feet_block.y+1)*self.level.tileheight
                            vel.y = 0
                            return

                        # resolve head collisions
                        new_head_block = new_feet_block + Vec2d(0, 3)
                        tile_there = self.getTile(new_head_block)
                        if tile_there.solid:
                            new_pos.y = (new_head_block.y-1-3)*self.level.tileheight
                            vel.y = 0
                            return

            def resolve_x(new_pos, vel, obj_size):
                if vel.x != 0:
                    adjust_x = 0
                    if sign(vel.x) == 1:
                        adjust_x = self.level.tilewidth
                    new_feet_block = (Vec2d(new_pos.x+adjust_x, new_pos.y) / Game.tile_size).do(int)
                    for y in range(obj_size.y):
                        new_body_block = Vec2d(new_feet_block.x, new_feet_block.y + y)
                        tile_there = self.getTile(new_body_block)
                        if tile_there.solid:
                            new_pos.x = (new_feet_block.x-sign(vel.x))*self.level.tilewidth
                            vel.x = 0
                            return
            # try resolving the collision both ways (y then x, x then y) and choose the one that results in the most velocity
            x_first_new_pos = Vec2d(new_pos)
            x_first_new_vel = Vec2d(obj.vel)
            resolve_x(x_first_new_pos, x_first_new_vel, obj.size)
            resolve_y(x_first_new_pos, x_first_new_vel, obj.size)

            y_first_new_pos = Vec2d(new_pos)
            y_first_new_vel = Vec2d(obj.vel)
            resolve_y(y_first_new_pos, y_first_new_vel, obj.size)
            resolve_x(y_first_new_pos, y_first_new_vel, obj.size)

            if x_first_new_vel.get_length_sqrd() > y_first_new_vel.get_length_sqrd():
                new_pos = x_first_new_pos
                obj.vel = x_first_new_vel
            else:
                new_pos = y_first_new_pos
                obj.vel = y_first_new_vel

            # apply velocity to position
            obj.pos = new_pos

            block_at_feet = (Vec2d(obj.pos.x + self.level.tilewidth / 2, obj.pos.y-1) / Game.tile_size).do(int)
            tile_at_feet = self.getTile(block_at_feet)
            on_ground = tile_at_feet.solid

            if obj.can_pick_up_stuff:
                # item pickups
                corner_block = (obj.pos / Game.tile_size).do(int)
                feet_block = ((obj.pos + Game.tile_size / 2) / Game.tile_size).do(int)
                for y in range(4): # you're 4 tiles high
                    block = feet_block + Vec2d(0, y)
                    tile = self.getTile(block)

                    # +1
                    if self.control_lemming - self.plus_ones_queued > 0:
                        if tile.id == self.tiles.enum.PlusOne:
                            self.plus_ones_queued += 1
                            self.setTile(block, self.tiles.enum.Air)
                        elif tile.id == self.tiles.enum.PlusForever:
                            self.plus_ones_queued = self.control_lemming
                    # land mine
                    if tile.mine:
                        if obj == char:
                            self.explode_queued = True
                        else:
                            self.physical_objects.append(Game.PhysicsObject(obj.pos, obj.vel,
                                pyglet.sprite.Sprite(self.animations['explosion'], batch=self.batch_level, group=self.group_fg),
                                Vec2d(1, 1), self.animations['explosion'].get_duration()))
                            obj.gone = True
                            obj.sprite.delete()
                            obj.sprite = None
                        self.setTile(block, self.tiles.enum.Air)

                # spikes
                if tile_at_feet.spike:
                    if obj == char:
                        self.spike_death_queued = True
                    else:
                        obj.gone = True
                        obj.sprite.delete()
                        obj.sprite = None
                    self.setTile(block_at_feet, self.tiles.enum.DeadBodyMiddle)
                    self.setTile(block_at_feet+Vec2d(1,0), self.tiles.enum.DeadBodyRight)
                    self.setTile(block_at_feet+Vec2d(-1,0), self.tiles.enum.DeadBodyLeft)

            if obj == char:
                # scroll the level
                normal_scroll_accel = 1200
                slow_scroll_accel = 1200
                desired_scroll = self.getDesiredScroll(Vec2d(obj.pos))
                scroll_diff = desired_scroll - self.scroll

                self.scroll += self.scroll_vel * dt
                for i in range(2):
                    if abs(scroll_diff[i]) < 10:
                        proposed_new_vel = self.scroll_vel[i] - sign(self.scroll_vel[i]) * normal_scroll_accel * dt
                        if sign(proposed_new_vel) != sign(self.scroll_vel[i]):
                            self.scroll_vel[i] = 0
                        else:
                            self.scroll_vel[i] = proposed_new_vel
                    elif abs(scroll_diff[i]) < abs(self.scroll_vel[i] * self.scroll_vel[i] / slow_scroll_accel):
                        if sign(self.scroll_vel[i]) == sign(scroll_diff[i]) != 0:
                            apply_scroll_accel = min(-self.scroll_vel[i] * self.scroll_vel[i] / scroll_diff[i], slow_scroll_accel)
                            self.scroll_vel[i] += apply_scroll_accel * dt
                    else:
                        self.scroll_vel[i] += sign(scroll_diff[i]) * normal_scroll_accel * dt

                # apply input to physics
                acceleration = 900
                max_speed = 200
                move_left = self.control_state[Game.Control.MoveLeft]
                move_right = self.control_state[Game.Control.MoveRight]
                if move_left and not move_right:
                    if obj.vel.x - acceleration * dt < -max_speed:
                        obj.vel.x = -max_speed
                    else:
                        obj.vel.x -= acceleration * dt

                    # switch sprite to running left
                    if on_ground:
                        if obj.sprite.image != self.animations['-lem_run']:
                            obj.sprite.image = self.animations['-lem_run']
                            obj.frame.new_image = obj.sprite.image
                elif move_right and not move_left:
                    if obj.vel.x + acceleration * dt > max_speed:
                        obj.vel.x = max_speed
                    else:
                        obj.vel.x += acceleration * dt

                    # switch sprite to running right
                    if on_ground:
                        if obj.sprite.image != self.animations['lem_run']:
                            obj.sprite.image = self.animations['lem_run']
                            obj.frame.new_image = obj.sprite.image
                else:
                    if on_ground:
                        # switch sprite to still
                        if obj.sprite.image != self.animations['lem_crazy']:
                            obj.sprite.image = self.animations['lem_crazy']
                            obj.frame.new_image = obj.sprite.image
                if self.control_state[Game.Control.Jump] and on_ground:
                    jump_velocity = 350
                    obj.vel.y = jump_velocity

                    # switch sprite to jump
                    animation_name = 'lem_jump'
                    if obj.vel.x < 0:
                        animation_name = '-' + animation_name
                    if obj.sprite.image != self.animations[animation_name]:
                        obj.sprite.image = self.animations[animation_name]
                        obj.frame.new_image = obj.sprite.image
                else:
                    self.jump_scheduled = False


            # gravity
            gravity_accel = 800
            if not on_ground:
                obj.vel.y -= gravity_accel * dt

            # friction
            friction_accel = 380
            if on_ground:
                if abs(obj.vel.x) < abs(friction_accel * dt):
                    obj.vel.x = 0
                else:
                    obj.vel.x += friction_accel * dt * -sign(obj.vel.x)
            
            if (on_ground and obj.vel.get_length_sqrd() == 0) and obj.is_belly_flop:
                # replace tiles it took up with dead body
                self.setTile(block_at_feet+Vec2d(0, 1), self.tiles.enum.DeadBodyMiddle)
                self.setTile(block_at_feet+Vec2d(1, 1), self.tiles.enum.DeadBodyRight)
                self.setTile(block_at_feet+Vec2d(-1, 1), self.tiles.enum.DeadBodyLeft)
                
                obj.gone = True
                obj.sprite.delete()
                obj.sprite = None

        char.frame.pos = char.pos
        char.frame.vel = char.vel

        # prepare sprites for drawing
        # physical objects
        for obj in self.physical_objects:
            if not obj.gone:
                pos = obj.pos + self.animation_offset[obj.sprite.image]
                obj.sprite.set_position(*pos)

        # lemmings
        for lemming in self.lemmings[self.control_lemming:]:
            if lemming.frame.new_image is not None:
                lemming.sprite.image = lemming.frame.new_image
            pos = lemming.frame.pos + self.animation_offset[lemming.sprite.image]
            lemming.sprite.set_position(*pos)

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

        # far background
        far_bgpos = Vec2d(-((self.scroll.x * 0.25) % self.sprite_bg_left.width), -(self.scroll.y * 0.10))
        if far_bgpos.y > 0:
            far_bgpos.y = 0
        if far_bgpos.y + self.sprite_bg_left.height < self.window.height:
            far_bgpos.y = self.window.height - self.sprite_bg_left.height
        far_bgpos.do(int)
        pyglet.gl.glLoadIdentity()
        pyglet.gl.glTranslatef(far_bgpos.x, far_bgpos.y, 0.0)
        self.batch_bg2.draw()

        # close background
        close_bgpos = Vec2d(-((self.scroll.x * 0.5) % self.sprite_hill_left.width), -(self.scroll.y * 0.20))
        if close_bgpos.y > 0:
            close_bgpos.y = 0
        close_bgpos.do(int)
        pyglet.gl.glLoadIdentity()
        pyglet.gl.glTranslatef(close_bgpos.x, close_bgpos.y, 0.0)
        self.batch_bg1.draw()

        # level 
        floored_scroll = -self.scroll.done(int)
        pyglet.gl.glLoadIdentity()
        pyglet.gl.glTranslatef(floored_scroll.x, floored_scroll.y, 0.0)
        self.batch_level.draw()

        # fps display
        pyglet.gl.glLoadIdentity()
        self.fps_display.draw()

    def blockAt(self, abs_pt):
        return (abs_pt / Game.tile_size).do(int)

    def getTile(self, block_pos):
        try:
            return self.tiles.info[self.level.layers[0].content2D[block_pos.x][block_pos.y]]
        except IndexError:
            return self.tiles.info[self.tiles.enum.Air]

    def setTile(self, block_pos, tile_id):
        self.level.layers[0].content2D[block_pos.x][block_pos.y] = tile_id
        if tile_id == 0:
            new_sprite = None
        else:
            new_sprite = pyglet.sprite.Sprite(
                self.level.indexed_tiles[tile_id][2], x=self.level.tilewidth * block_pos.x,
                y=self.level.tileheight * block_pos.y, batch=self.batch_level, group=self.layer_group[0])

        self.sprites[0][block_pos.x][block_pos.y] = new_sprite

    def garbage_collect(self, dt):
        if self.physical_objects is not None:
            self.physical_objects = filter(lambda obj: not obj.gone, self.physical_objects)

    def createWindow(self):
        self.window = pyglet.window.Window(width=853, height=480, vsync=False)
        self.window.set_handler('on_draw', self.on_draw)
        self.window.set_handler('on_key_press', self.on_key_press)
        self.window.set_handler('on_key_release', self.on_key_release)

    def load(self, level_filename):
        self.level = tiledtmxloader.TileMapParser().parse_decode(level_filename)
        self.level.load(tiledtmxloader.ImageLoaderPyglet())

        self.tiles = TileSet(self.level.tile_sets[0])

        Game.tile_size = Vec2d(self.level.tilewidth, self.level.tileheight)

        # load tiles into sprites
        self.next_group_num = 0
        self.group_bg2 = pyglet.graphics.OrderedGroup(self.getNextGroupNum())
        self.group_bg1 = pyglet.graphics.OrderedGroup(self.getNextGroupNum())

        self.sprites = [] # [layer][x][y]
        for i, layer in enumerate(self.level.layers):
            self.sprites.append([])
            for x in range(layer.width):
                self.sprites[i].append([])
                for y in range(layer.height):
                    self.sprites[i][x].append(None)
                    
        self.layer_group = []

        for layer_index, layer in enumerate(self.level.layers):
            group = pyglet.graphics.OrderedGroup(self.getNextGroupNum())
            self.layer_group.append(group)
            for xtile in range(layer.width):
                layer.content2D[xtile].reverse()
            for ytile in range(layer.height):
                # To compensate for pyglet's upside-down y-axis, the Sprites are
                # placed in rows that are backwards compared to what was loaded
                # into the map. The next operation puts all rows upside-down.
                for xtile in range(layer.width):
                    image_id = layer.content2D[xtile][ytile]
                    if image_id:
                        # o_x and o_y are offsets. They are not helpful here.
                        o_x, o_y, image_file = self.level.indexed_tiles[image_id]
                        self.sprites[layer_index][xtile][ytile] = pyglet.sprite.Sprite(image_file,
                            x=self.level.tilewidth * xtile,
                            y=self.level.tileheight * ytile,
                            batch=self.batch_level, group=group)

        had_player_layer = False
        had_start_point = False
        def translate_y(y, obj_height=0):
            return self.level.height * self.level.tileheight - y - obj_height
        self.labels = []
        for obj_group in self.level.object_groups:
            group = pyglet.graphics.OrderedGroup(self.getNextGroupNum())
            self.layer_group.append(group)
            if obj_group.name == 'PlayerLayer':
                self.group_char = group
                had_player_layer = True

            for obj in obj_group.objects:
                if obj.type == 'StartPoint':
                    self.start_point = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    had_start_point = True
                elif obj.type == 'Text':
                    try:
                        font_size = int(obj.properties['font_size'])
                    except KeyError:
                        font_size = 20
                    self.labels.append(pyglet.text.Label(obj.properties['text'], font_name="Arial", font_size=font_size, 
                        x=obj.x, y=translate_y(obj.y, obj.height), batch=self.batch_level, group=group,
                        color=(0, 0, 0, 255), multiline=True, width=obj.width, height=obj.height, anchor_x='left', anchor_y='bottom'))

        if not had_start_point:
            assert False, "Level missing start point."

        if not had_player_layer:
            print("Level was missing PlayerLayer")
            self.group_char = pyglet.graphics.OrderedGroup(self.getNextGroupNum())
        self.group_fg = pyglet.graphics.OrderedGroup(self.getNextGroupNum())

    def execute(self):
        self.loadImages()
        self.createWindow()
        self.start()

        pyglet.app.run()
