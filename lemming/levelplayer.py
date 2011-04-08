from __future__ import division, print_function, unicode_literals; range = xrange

from tiles import TileSet
from vec2d import Vec2d
import tiledtmxloader
from screen import Screen

import pyglet
import sys
import itertools
import math
import random
import game

import os

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

class mdict(dict):
    def __setitem__(self, key, value):
        """add the given value to the list of values for this key"""
        self.setdefault(key, []).append(value)

tile_size = None
lemming_count = 9
lemming_response_time = 0.40

class Control:
    MoveLeft = 0
    MoveRight = 1
    MoveUp = 2
    MoveDown = 3
    BellyFlop = 4
    Freeze = 5
    Explode = 6

class LemmingFrame(object):
    def __init__(self, pos, vel, next_node, new_image=None, on_ladder=False):
        self.pos = pos
        self.vel = vel
        self.on_ladder = on_ladder
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
        self.explodable = False
        self.on_ladder = False

    def delete(self):
        self.gone = True
        if self.sprite is not None:
            self.sprite.delete()
            self.sprite = None

    def think(self, dt):
        pass

class Lemming(PhysicsObject):
    def __init__(self, sprite, frame=None):
        if frame is not None:
            super(Lemming, self).__init__(frame.pos, frame.vel, sprite, Vec2d(1, 4), can_pick_up_stuff=True)
        else:
            super(Lemming, self).__init__(None, None, sprite, Vec2d(1, 4), can_pick_up_stuff=True)
        self.frame = frame
        self.gone = False

class Gunner(PhysicsObject):
    def __init__(self, pos, size, group, batch, game):
        super(Gunner, self).__init__(pos, Vec2d(0, 0), pyglet.sprite.Sprite(game.animations['gunner_still'],
            x=pos.x, y=pos.y, group=group, batch=batch), size, direction=0)
        self.game = game
        self.explodable = True
        self.can_shoot = True
        self.shoot_delay = 2

    def think(self, dt):
        if self.game.control_lemming >= len(self.game.lemmings):
            return

        player_pos = (self.game.lemmings[self.game.control_lemming].pos / tile_size).do(int)
        player_size = self.game.lemmings[self.game.control_lemming].size
        my_pos = (self.pos / tile_size).do(int)

        # if we can trace a path to lem then look at him
        see_distance = 30
        can_see = False
        look_direction = sign(player_pos.x - my_pos.x)
        eye_y = self.size.y - 1
        for x in range(see_distance):
            test_pos = Vec2d(my_pos.x + x * look_direction, my_pos.y + eye_y)
            if self.game.getBlockIsSolid(test_pos):
                break
            if test_pos.x >= player_pos.x and test_pos.x < player_pos.x + player_size.x and test_pos.y >= player_pos.y and test_pos.y < player_pos.y + player_size.y:
                can_see = True
                break
        if can_see:
            self.changeDirection(look_direction)
            self.wantToShoot()
        else:
            self.changeDirection(0)

    def wantToShoot(self):
        if not self.can_shoot:
            return
        self.can_shoot = False
        def recharge(dt):
            self.can_shoot = True
        pyglet.clock.schedule_once(recharge, self.shoot_delay)

        gun_offset = Vec2d(64*self.direction, 16)
        bullet_init_vel = Vec2d(1100*self.direction, 200)
        self.game.spawnBullet(self.pos+gun_offset, self.vel+bullet_init_vel)

        if self.direction < 0:
            name = '-gunner_shoot'
        elif self.direction > 0:
            name = 'gunner_shoot'
        self.sprite.image = self.game.animations[name]

    def changeDirection(self, new_dir):
        if new_dir == self.direction:
            return
        self.direction = new_dir
        if self.direction < 0:
            name = '-gunner_point'
        elif self.direction > 0:
            name = 'gunner_point'
        else:
            name = 'gunner_still'

        self.sprite.image = self.game.animations[name]

class Bomb(PhysicsObject):
    def __init__(self, pos, vel, fuse, sprite, game):
        super(Bomb, self).__init__(pos, vel, sprite, Vec2d(1, 1))
        self.game = game
        self.fuse = fuse
    
    def think(self, dt):
        self.fuse -= dt

        if self.fuse <= 0:
            self.game.handleExplosion(self.pos, self.vel)
            self.delete()

class Bullet(PhysicsObject):
    def __init__(self, pos, vel, sprite, game):
        max_bullet_life = 10
        super(Bullet, self).__init__(pos, vel, sprite, Vec2d(1, 1), life=max_bullet_life)
        self.game = game

    def think(self, dt):
        # if we're going too slow, die
        die_threshold = 100
        if abs(self.vel.x) < die_threshold:
            self.delete()
            return

        if self.game.control_lemming >= len(self.game.lemmings):
            return

        # if we hit something solid, die
        my_block = (self.pos / tile_size).do(int)
        if self.game.getBlockIsSolid(my_block):
            self.delete()
            return

        # test for hitting player
        player_pos = (self.game.lemmings[self.game.control_lemming].pos / tile_size).do(int)
        player_size = self.game.lemmings[self.game.control_lemming].size
        if my_block.x >= player_pos.x and my_block.x < player_pos.x + player_size.x and my_block.y >= player_pos.y and my_block.y < player_pos.y + player_size.y:
            self.game.hitByBullet()
            self.delete()
            return


class Monster(PhysicsObject):
    def __init__(self, pos, size, group, batch, game, direction, throw_vel=None):
        if direction > 0:
            negate = ''
        else:
            negate = '-'
        super(Monster, self).__init__(pos, Vec2d(0, 0), pyglet.sprite.Sprite(game.animations[negate+'monster_still'],
            x=pos.x, y=pos.y, group=group, batch=batch), size, direction=direction)
        self.game = game
        self.grabbing = False
        self.explodable = True
        if throw_vel is None:
            self.throw_vel = Vec2d(600*direction, 600)
        else:
            self.throw_vel = throw_vel

    def think(self, dt):
        if self.game.control_lemming < len(self.game.lemmings):
            player_pos = (self.game.lemmings[self.game.control_lemming].pos / tile_size).do(int)
            my_pos = (self.pos / tile_size).do(int)
            if self.direction > 0:
                get_him = player_pos.x >= my_pos.x + 2 and player_pos.x <= my_pos.x+5
            else:
                get_him = player_pos.x <= my_pos.x + 2 and player_pos.x >= my_pos.x-3

            if get_him and (player_pos.y == my_pos.y or player_pos.y == my_pos.y + 1) and not self.grabbing:
                self.grabbing = True
                self.game.getGrabbedBy(self, self.throw_vel)

class ButtonResponder(object):
    def toggle(self):
        pass

class PlatformObject(object):
    def solidAt(self, block):
        return False

class ConveyorBelt(ButtonResponder):
    def __init__(self, pos, size, sprite, game, state='on', direction=1):
        self.pos = pos
        self.size = size
        self.sprite = sprite
        self.game = game
        self.state = state == 'on'
        self.direction = sign(direction)
        # reversed because animation is backwards
        self.animations = {-1: self.game.animations['belt_on'], 1: self.game.animations['-belt_on']}

        self.toggle()
        self.toggle()

    def toggle(self):
        self.state = not self.state

        if self.state:
            self.sprite.image = self.animations[self.direction]

            if self.direction > 0:
                new_tile = self.game.tiles.enum.BeltRight
            else:
                new_tile = self.game.tiles.enum.BeltLeft
        else:
            self.sprite.image = self.game.animations['belt_off']
            new_tile = self.game.tiles.enum.SolidInvisible

        it = Vec2d(0, 0)
        for it.x in range(self.size.x):
            for it.y in range(self.size.y):
                self.game.setTile(self.pos+it, new_tile)

class Bridge(ButtonResponder, PlatformObject):
    def __init__(self, pos, size, state, up_sprite, down_sprite):
        self.pos = pos
        self.size = size
        self.state_up = state == 'up'
        self.up_sprite = up_sprite
        self.down_sprite = down_sprite

        self.toggle()
        self.toggle()

    def toggle(self):
        self.state_up = not self.state_up
        self.up_sprite.visible = self.state_up
        self.down_sprite.visible = not self.state_up

    def solidAt(self, pos):
        rel_pos = pos - self.pos
        if self.state_up:
            return rel_pos.x == self.size.x - 1 and rel_pos.y >= 0 and rel_pos.y < self.size.y
        else: # down
            return rel_pos.y == 0 and rel_pos.x >= 0 and rel_pos.x < self.size.x

class TrapDoor(object):
    def __init__(self, pos, size, state, sprite):
        self.pos = pos
        self.size = size
        self.state = state
        self.sprite = sprite

        self.toggle()
        self.toggle()

    def toggle(self):
        if self.state == 'closed':
            self.state = 'open'
            self.sprite.visible = False
        else:
            self.state = 'closed'
            self.sprite.visible = True

    def solidAt(self, pos):
        rel_pos = pos - self.pos
        if self.state == 'open':
            return False
        else:
            return rel_pos.y >= 0 and rel_pos.y < self.size.y and rel_pos.x >= 0 and rel_pos.x < self.size.x

class AbstractButton(object):
    def hit(self, who_done_it):
        pass

class Gear(AbstractButton):
    def __init__(self, pos, size, button_id, sprite, game):
        self.pos = pos
        self.size = size
        self.button_id = button_id
        self.sprite = sprite
        self.game = game
        self.turning = True

    def hit(self, who_done_it):
        if not self.turning:
            return
        self.turning = False

        if self.game.control_lemming >= len(self.game.lemmings):
            is_char = False
        else:
            is_char = self.game.lemmings[self.game.control_lemming] == who_done_it
        
        if is_char:
            self.game.detatch_queued = True
        else:
            who_done_it.delete()

        self.game.hitButtonId(self.button_id)
        self.sprite.image = self.game.animations['gear_bloody']
        self.game.sfx['spike_death'].play()
        
class Button(AbstractButton):
    def __init__(self, pos, button_id, up_sprite, down_sprite, delay, game):
        self.pos = pos
        self.button_id = button_id
        self.up_sprite = up_sprite
        self.down_sprite = down_sprite
        self.delay = delay
        self.game = game
        self.changeState(False)

    def hit(self, who_done_it):
        if self.state_down:
            return

        self.changeState(True)
        self.game.hitButtonId(self.button_id)
        self.game.sfx['button_click'].play()

        def goBackUp(dt):
            self.changeState(False)
            self.game.sfx['button_unclick'].play()
        pyglet.clock.schedule_once(goBackUp, self.delay)

    def changeState(self, value):
        self.state_down = value
        if self.state_down:
            self.up_sprite.visible = False
            self.down_sprite.visible = True
        else:
            self.up_sprite.visible = True
            self.down_sprite.visible = False

class BombSpawner(ButtonResponder):
    def __init__(self, pos, size, game, delay, state='on'):
        self.pos = pos
        self.size = size
        self.game = game
        self.delay = delay
        self.state = state == 'on'

        self.game.intervals.append(self.spawn)
        self.toggle()
        self.toggle()

    def toggle(self):
        self.state = not self.state

        if self.state:
            pyglet.clock.schedule_interval(self.spawn, self.delay)
        else:
            pyglet.clock.unschedule(self.spawn)

    def spawn(self, dt):
        # pick random location within my size
        pos = self.pos + Vec2d(random.random() * self.size.x, random.random() * self.size.y)

        # pick random fuse length
        fuse = 1 + random.random() * 3

        # vary the velocity by tiny amounts
        vel = Vec2d(random.random() * 100 - 50, random.random() * 100 - 50)

        self.game.spawnBomb(pos, vel, fuse)
        

class LevelPlayer(Screen):
    def getNextGroupNum(self):
        val = self.next_group_num
        self.next_group_num += 1
        return val

    def loadSoundEffects(self):
        self.sfx = {
            'blast': pyglet.resource.media('sound/blast.mp3', streaming=False),
            'button_click': pyglet.resource.media('sound/button_click.mp3', streaming=False),
            'button_unclick': pyglet.resource.media('sound/button_unclick.mp3', streaming=False),
            'coin_pickup': pyglet.resource.media('sound/coin_pickup.mp3', streaming=False),
            'game_over': pyglet.resource.media('sound/game_over.mp3', streaming=False),
            'gunshot': pyglet.resource.media('sound/gunshot.mp3', streaming=False),
            'jump': pyglet.resource.media('sound/jump.mp3', streaming=False),
            'ladder': pyglet.resource.media('sound/ladder.mp3', streaming=False),
            'level_start': pyglet.resource.media('sound/level_start.mp3', streaming=False),
            'mine_beep': pyglet.resource.media('sound/mine_beep.mp3', streaming=False),
            'running': pyglet.resource.media('sound/running.mp3', streaming=False),
            'spike_death': pyglet.resource.media('sound/spike_death.mp3', streaming=False),
            'weee': pyglet.resource.media('sound/weee.mp3', streaming=False),
            'winnar': pyglet.resource.media('sound/winnar.mp3', streaming=False),
            'woopee': pyglet.resource.media('sound/woopee.mp3', streaming=False),
        }
        self.running_sound_player = pyglet.media.Player()
        self.running_sound_player.eos_action = pyglet.media.Player.EOS_LOOP

    def setRunningSound(self, source):
        if source is None:
            self.running_sound_player.pause()
        else:
            self.running_sound_player.next()
            self.running_sound_player.queue(source)
            self.running_sound_player.play()

    def loadImages(self):
        # load animations
        with pyglet.resource.file('animations.txt') as fd:
            animations_txt = fd.read()
        lines = animations_txt.split('\n')
        self.animations = {}
        self.animation_offset = {}
        for full_line in lines:
            line = full_line.strip()
            if line.startswith('#') or len(line) == 0:
                continue
            props, frames_txt = line.split('=')

            name, delay, loop, off_x, off_y, size_x, size_y = props.strip().split(':')
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
            self.animation_offset[rev_animation] = Vec2d(int(off_x) + int(size_x), -int(off_y))

        
        self.img_hud = pyglet.resource.image('hud.png')
        self.img_bullet = pyglet.resource.image('bullet.png')
        self.img_bomb = pyglet.resource.image('bomb.png')


        if self.level.properties.has_key('bg_art'):
            img = pyglet.resource.image(self.level.properties['bg_art'])
            self.sprite_bg_left = pyglet.sprite.Sprite(img, batch=self.batch_bg2)
            self.sprite_bg_right = pyglet.sprite.Sprite(img, batch=self.batch_bg2)

            self.sprite_bg_left.set_position(0, 0)
            self.sprite_bg_right.set_position(self.sprite_bg_left.width, 0)
        else:
            self.sprite_bg_left = None
            self.sprite_bg_right = None

            
        if self.level.properties.has_key('fg_art'):
            img = pyglet.resource.image(self.level.properties['fg_art'])
            self.sprite_bg2_left = pyglet.sprite.Sprite(img, batch=self.batch_bg1)
            self.sprite_bg2_right = pyglet.sprite.Sprite(img, batch=self.batch_bg1)

            self.sprite_bg2_left.set_position(0, 0)
            self.sprite_bg2_right.set_position(self.sprite_bg2_left.width, 0)
        else:
            self.sprite_bg2_left = None
            self.sprite_bg2_right = None

    def loadConfig(self):
        self.controls = {
            pyglet.window.key.LEFT: Control.MoveLeft,
            pyglet.window.key.RIGHT: Control.MoveRight,
            pyglet.window.key.UP: Control.MoveUp,
            pyglet.window.key.DOWN: Control.MoveDown,
            pyglet.window.key._1: Control.BellyFlop,
            pyglet.window.key._2: Control.Explode,
            pyglet.window.key._3: Control.Freeze,
        }

    def __init__(self, game, level_fd):
        self.game = game
        self.level = None
        self.physical_objects = []
        self.button_responders = mdict()
        self.platform_objects = []
        self.buttons = {}
        self.victory = {}
        self.intervals = []

        self.batch_bg2 = pyglet.graphics.Batch()
        self.batch_bg1 = pyglet.graphics.Batch()
        self.batch_level = pyglet.graphics.Batch()
        self.batch_static = pyglet.graphics.Batch()

        self.bg_music_player = pyglet.media.Player()
        self.bg_music_player.eos_action = pyglet.media.Player.EOS_LOOP
        self.bg_music_player.volume = 0.50

        self.loadConfig()

        self.level_fd = level_fd

    def getDesiredScroll(self, point):
        scroll = Vec2d(point) - Vec2d(self.game.window.width, self.game.window.height) / 2
        if scroll.x < 0:
            scroll.x = 0
        if scroll.y < 0:
            scroll.y = 0
        if scroll.x > self.level.width * self.level.tilewidth - self.game.window.width:
            scroll.x = self.level.width * self.level.tilewidth  - self.game.window.width
        if scroll.y > self.level.height * self.level.tileheight - self.game.window.height:
            scroll.y = self.level.height * self.level.tileheight  - self.game.window.height
        return scroll

    def clear(self):
        self.game.window.remove_handlers()

        for interval in self.intervals:
            pyglet.clock.unschedule(interval)
        self.intervals = None

        self.bg_music_player.pause()
        self.bg_music_player = None

        self.lemmings = None
        self.control_state = None

        self.level = None
        self.physical_objects = None
        self.button_responders = None
        self.platform_objects = None
        self.buttons = None
        self.victory = None

        self.batch_bg2 = None
        self.batch_bg1 = None
        self.batch_level = None
        self.batch_static = None

        self.running_sound_player.pause()
        self.running_sound_player = None


    def start(self):
        self.load()
        
        self.game.window.set_handler('on_draw', self.on_draw)
        self.game.window.set_handler('on_key_press', self.on_key_press)
        self.game.window.set_handler('on_key_release', self.on_key_release)

        self.scroll = self.getDesiredScroll(self.start_point)
        self.scroll_vel = Vec2d(0, 0)
        self.last_scroll_delta = Vec2d(0, 0)
        self.lemmings = [None] * lemming_count
        self.control_state = [False] * (len(dir(Control)) - 2)
        self.control_lemming = 0
        self.held_by = None
        self.handled_victory = False

        self.explode_queued = False # true when the user presses the button until an update happens
        self.bellyflop_queued = False
        self.freeze_queued = False
        self.plus_ones_queued = 0
        self.detatch_queued = False

        # resets variables based on level and begins the game
        # generate data for each lemming
        for i in range(len(self.lemmings)):
            sprite = pyglet.sprite.Sprite(self.animations['lem_crazy'], batch=self.batch_level, group=self.group_char)
            if i > 0:
                sprite.opacity = 128
            self.lemmings[i] = Lemming(sprite, None)

        # generate frames for trails
        head_frame = LemmingFrame(Vec2d(self.start_point), Vec2d(0, 0), None, on_ladder=False)
        lemming_index = len(self.lemmings) - 1
        self.lemmings[lemming_index].frame = head_frame
        lemming_index -= 1
        lemming_frame_count = 1
        while game.target_fps * lemming_response_time * (len(self.lemmings)-1) > lemming_frame_count:
            head_frame = LemmingFrame(Vec2d(head_frame.pos), Vec2d(head_frame.vel), head_frame, on_ladder=False)
            lemming_frame_count += 1
            if int((len(self.lemmings) - 1 - lemming_index) * game.target_fps * lemming_response_time) == lemming_frame_count:
                self.lemmings[lemming_index].frame = head_frame
                lemming_index -= 1

        pyglet.clock.schedule_interval(self.update, 1/game.target_fps)
        self.intervals.append(self.update)
        pyglet.clock.schedule_interval(self.garbage_collect, 10)
        self.intervals.append(self.garbage_collect)
        self.fps_display = pyglet.clock.ClockDisplay()

        self.sfx['level_start'].play()

        self.sprite_hud = pyglet.sprite.Sprite(self.img_hud, batch=self.batch_static, x=0, y=self.game.window.height-self.img_hud.height)

    def getGrabbedBy(self, monster, throw_vel):
        self.lemmings[self.control_lemming].frame.vel = Vec2d(0, 0)
        self.lemmings[self.control_lemming].sprite.visible = False
        self.held_by = monster

        # hide sprite until throw animation is over
        negate = ''
        if monster.direction < 0:
            negate = '-'
        monster.sprite.image = self.animations[negate+'monster_throw']
        def reset_animation():
            monster.sprite.image = self.animations[negate+'monster_still']
            self.lemmings[self.control_lemming].frame.vel = throw_vel
            self.lemmings[self.control_lemming].sprite.visible = True
            self.held_by = None
            def not_grabbing(dt):
                monster.grabbing = False
            pyglet.clock.schedule_once(not_grabbing, 2)
            monster.sprite.remove_handler('on_animation_end', reset_animation)

            self.sfx[['weee', 'woopee'][random.randint(0, 1)]].play()
        monster.sprite.set_handler('on_animation_end', reset_animation)

    def detatchHeadLemming(self):
        head_lemming = self.lemmings[self.control_lemming]

        head_lemming.sprite.delete()
        head_lemming.sprite = None

        self.control_lemming += 1
        if self.control_lemming == len(self.lemmings):
            # game over
            self.handleGameOver()
            return
        head_lemming = self.lemmings[self.control_lemming]

        head_lemming.sprite.opacity = 255
        head_lemming.frame.prev_node = None

    def handleExplosion(self, pos, vel, caused_by_self=False):
        self.sfx['blast'].play()
        self.physical_objects.append(PhysicsObject(pos, vel,
            pyglet.sprite.Sprite(self.animations['explosion'], batch=self.batch_level, group=self.group_fg),
            Vec2d(1, 1), self.animations['explosion'].get_duration()))

        explosion_power = 4
        it = Vec2d(0, 0)
        block_pos = (pos / tile_size).do(int)
        for it.y in range(explosion_power * 2):
            for it.x in range(explosion_power * 2):
                pt = block_pos + it - Vec2d(explosion_power, explosion_power)
                if pt.get_distance(block_pos) <= explosion_power:
                    # affect block
                    tile = self.getTile(pt)
                    if tile.breakable:
                        self.setTile(pt, self.tiles.enum.Air)

        # see if we need to blow up any monsters
        for obj in self.physical_objects:
            if obj.gone:
                continue
            if obj.explodable:
                if (obj.pos + (obj.size * tile_size) / 2).get_distance(pos) <= explosion_power * self.level.tilewidth:
                    # kill monster
                    obj.delete()

    def handleGameOver(self):
        self.bg_music_player.pause()
        self.sfx['game_over'].play()
        def restart(dt):
            self.game.restartLevel()
        pyglet.clock.schedule_once(restart, 4)

    def handleVictory(self):
        self.bg_music_player.pause()
        self.sfx['winnar'].play()
        def goNext(dt):
            self.game.gotoNextLevel()
        pyglet.clock.schedule_once(goNext, 4)

    def update(self, dt):
        if self.control_lemming < len(self.lemmings):
            if self.explode_queued:
                self.explode_queued = False

                if self.held_by is not None:
                    explosion_pos = self.held_by.pos+self.held_by.size / 2 * tile_size
                    self.handleExplosion(explosion_pos, self.held_by.vel, caused_by_self=True)

                    self.held_by.delete()
                    self.held_by = None
                else:
                    old_head_lemming = self.lemmings[self.control_lemming]
                    self.handleExplosion(old_head_lemming.frame.pos+Vec2d(0, 2), old_head_lemming.frame.vel, caused_by_self=True)

                self.detatchHeadLemming()
            elif self.detatch_queued and self.held_by is None:
                self.detatch_queued = False
                self.detatchHeadLemming()
            elif self.bellyflop_queued and self.held_by is None:
                self.bellyflop_queued = False

                old_head_lemming = self.lemmings[self.control_lemming]
                direction = sign(old_head_lemming.frame.vel.x)
                if direction < 0:
                    animation = self.animations['-lem_belly_flop']
                else:
                    direction = 1
                    animation = self.animations['lem_belly_flop']
                self.physical_objects.append(PhysicsObject(old_head_lemming.frame.pos,
                    old_head_lemming.frame.vel, pyglet.sprite.Sprite(animation, batch=self.batch_level, group=self.group_fg),
                    Vec2d(4, 1), can_pick_up_stuff=True, is_belly_flop=True, direction=direction))

                self.detatchHeadLemming()

                self.sfx[['weee', 'woopee'][random.randint(0, 1)]].play()

        # add more lemmings
        while self.plus_ones_queued > 0 and self.control_lemming > 0:
            self.plus_ones_queued -= 1
            self.control_lemming -= 1
            for i in range(self.control_lemming, len(self.lemmings)-1):
                self.lemmings[i] = self.lemmings[i+1]
            # add the missing frames
            old_last_frame = self.lemmings[-2].frame
            last_lem = Lemming(pyglet.sprite.Sprite(self.animations['lem_crazy'], batch=self.batch_level, group=self.group_char),
                LemmingFrame(Vec2d(old_last_frame.pos), Vec2d(old_last_frame.vel), None, on_ladder=old_last_frame.on_ladder))
            self.lemmings[-1] = last_lem
            last_lem.sprite.opacity = 128
            node = last_lem.frame
            for i in range(int(game.target_fps * lemming_response_time)):
                node = LemmingFrame(Vec2d(old_last_frame.pos), Vec2d(old_last_frame.vel), node, on_ladder=old_last_frame.on_ladder)
            old_last_frame.next_node = node
            node.prev_node = old_last_frame

        # lemming trails
        if self.control_lemming < len(self.lemmings):
            char = self.lemmings[self.control_lemming]
            char.frame = LemmingFrame(Vec2d(char.frame.pos), Vec2d(char.frame.vel), char.frame, on_ladder=char.frame.on_ladder)

            for lemming in self.lemmings[self.control_lemming+1:]:
                lemming.frame = lemming.frame.prev_node
            self.lemmings[-1].frame.next_node = None

            char.pos = char.frame.pos
            char.vel = char.frame.vel
            char.on_ladder = char.frame.on_ladder
        else:
            char = None

        # physics
        for obj in itertools.chain(self.physical_objects, [char]):
            if obj is None or obj.gone:
                continue
            obj.think(dt)

            if obj == char and self.held_by is not None:
                continue

            if obj.life is not None:
                obj.life -= dt
                if obj.life <= 0:
                    obj.delete()
                    continue

            apply_belt_velocity = 0

            # collision with solid blocks
            new_pos = obj.pos + obj.vel * dt
            def resolve_y(new_pos, vel, obj_size):
                if obj.on_ladder:
                    return

                new_feet_block = (new_pos / tile_size).do(int)
                tile_there = self.getTile(new_feet_block)

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
                    block_solid = self.getBlockIsSolid(new_feet_block)
                    # resolve feet collisions
                    if block_solid:
                        new_pos.y = (new_feet_block.y+1)*self.level.tileheight
                        vel.y = 0
                        return

                    # resolve head collisions
                    new_head_block = new_feet_block + Vec2d(0, obj_size.y - 1)
                    block_solid = self.getBlockIsSolid(new_head_block)
                    if block_solid:
                        new_pos.y = (new_head_block.y-1-3)*self.level.tileheight
                        vel.y = 0
                        return

            def resolve_x(new_pos, vel, obj_size):
                if obj.on_ladder:
                    return

                if vel.x != 0:
                    adjust_x = 0
                    if sign(vel.x) == 1:
                        adjust_x = self.level.tilewidth
                    new_feet_block = (Vec2d(new_pos.x+adjust_x, new_pos.y) / tile_size).do(int)
                    for y in range(obj_size.y):
                        new_body_block = Vec2d(new_feet_block.x, new_feet_block.y + y)
                        block_solid = self.getBlockIsSolid(new_body_block)
                        if block_solid:
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

            block_at_feet = (Vec2d(obj.pos.x + self.level.tilewidth / 2, obj.pos.y-1) / tile_size).do(int)
            tile_at_feet = self.getTile(block_at_feet)
            block_at_feet_solid = self.getBlockIsSolid(block_at_feet)
            on_ground = block_at_feet_solid

            if not on_ground and not obj.on_ladder:
                self.setRunningSound(None)

            if obj.can_pick_up_stuff:
                # item pickups
                corner_block = (obj.pos / tile_size).do(int)
                feet_block = ((obj.pos + tile_size / 2) / tile_size).do(int)
                it = Vec2d(0, 0)
                for it.y in range(obj.size.y):
                    for it.x in range(obj.size.x):
                        block = corner_block + it
                        tile = self.getTile(block)

                        # +1
                        if self.control_lemming - self.plus_ones_queued > 0:
                            if tile.id == self.tiles.enum.PlusOne:
                                self.plus_ones_queued += 1
                                self.setTile(block, self.tiles.enum.Air)

                                sfx_player = self.sfx['coin_pickup'].play()
                                sfx_player.pitch = 2 - (len(self.lemmings) - self.control_lemming - 1) / len(self.lemmings)
                            elif tile.id == self.tiles.enum.PlusForever:
                                self.plus_ones_queued = self.control_lemming

                                sfx_player = self.sfx['coin_pickup'].play()
                                sfx_player.pitch = 1
                        # land mine
                        if tile.mine:
                            if obj == char:
                                self.explode_queued = True
                            else:
                                self.handleExplosion(block * tile_size, Vec2d(0, 0))
                                obj.delete()
                            self.setTile(block, self.tiles.enum.Air)
                            self.sfx['mine_beep'].play()

                        # buttons
                        button_to_activate = None
                        try:
                            button_to_activate = self.buttons[tuple(block)]
                        except KeyError:
                            pass
                        if button_to_activate is not None:
                            button_to_activate.hit(obj)

                        # victory
                        if self.isVictory(block) and not self.handled_victory:
                            self.handled_victory = True
                            self.handleVictory()

                # spikes
                if tile_at_feet.spike:
                    if obj == char:
                        self.detatch_queued = True
                    else:
                        obj.delete()
                    if obj.is_belly_flop:
                        self.setTile(block_at_feet, self.tiles.enum.DeadBodyMiddle)
                        self.setTile(block_at_feet+Vec2d(1,0), self.tiles.enum.DeadBodyRight)
                        self.setTile(block_at_feet+Vec2d(-1,0), self.tiles.enum.DeadBodyLeft)
                    else:
                        self.setTile(block_at_feet, self.tiles.enum.DeadBodyMiddle)

                        negate = ''
                        if obj.vel.x < 0:
                            negate = '-'
                        self.physical_objects.append(PhysicsObject(obj.pos, Vec2d(0,0),
                            pyglet.sprite.Sprite(self.animations[negate+'lem_die'], batch=self.batch_level, group=self.group_fg),
                            obj.size, self.animations['lem_die'].get_duration()))

                    self.sfx['spike_death'].play()

            if tile_at_feet.belt is not None:
                belt_velocity = 800
                apply_belt_velocity = tile_at_feet.belt * belt_velocity * dt

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
                move_left = self.control_state[Control.MoveLeft]
                move_right = self.control_state[Control.MoveRight]
                move_up = self.control_state[Control.MoveUp]
                move_down = self.control_state[Control.MoveDown]
                if not move_up and (move_left or move_right or move_down):
                    obj.on_ladder = False
                ladder_at_feet = self.getTile(block_at_feet, 1)
                if obj.on_ladder and not ladder_at_feet.ladder:
                    obj.on_ladder = False
                if move_left and not move_right:
                    if obj.vel.x - acceleration * dt < -max_speed:
                        obj.vel.x += min(-max_speed - obj.vel.x, 0)
                    else:
                        obj.vel.x -= acceleration * dt

                    # switch sprite to running left
                    if on_ground:
                        if obj.sprite.image != self.animations['-lem_run']:
                            obj.sprite.image = self.animations['-lem_run']
                            obj.frame.new_image = obj.sprite.image

                            self.setRunningSound(self.sfx['running'])
                elif move_right and not move_left:
                    if obj.vel.x + acceleration * dt > max_speed:
                        obj.vel.x += max(max_speed - obj.vel.x, 0)
                    else:
                        obj.vel.x += acceleration * dt

                    # switch sprite to running right
                    if on_ground:
                        if obj.sprite.image != self.animations['lem_run']:
                            obj.sprite.image = self.animations['lem_run']
                            obj.frame.new_image = obj.sprite.image

                            self.setRunningSound(self.sfx['running'])
                else:
                    if on_ground:
                        # switch sprite to still
                        if obj.sprite.image != self.animations['lem_crazy']:
                            obj.sprite.image = self.animations['lem_crazy']
                            obj.frame.new_image = obj.sprite.image

                            self.setRunningSound(None)
                ladder_velocity = 200
                if move_up and ladder_at_feet.ladder:
                    obj.on_ladder = True
                    obj.vel.y = 0
                    obj.vel.x = 0
                    obj.pos.y += ladder_velocity * dt

                    # switch sprite to ladder
                    if obj.sprite.image != self.animations['lem_climb']:
                        obj.sprite.image = self.animations['lem_climb']
                        obj.frame.new_image = obj.sprite.image

                        self.setRunningSound(self.sfx['ladder'])
                elif move_down and ladder_at_feet.ladder:
                    obj.on_ladder = True
                    obj.vel.x = 0
                    obj.pos.y -= ladder_velocity * dt

                    # switch sprite to ladder
                    if obj.sprite.image != self.animations['lem_climb']:
                        obj.sprite.image = self.animations['lem_climb']
                        obj.frame.new_image = obj.sprite.image

                        self.setRunningSound(self.sfx['ladder'])
                elif move_up and on_ground:
                    jump_velocity = 350
                    obj.vel.y = jump_velocity

                    # switch sprite to jump
                    animation_name = 'lem_jump'
                    if obj.vel.x < 0:
                        animation_name = '-' + animation_name
                    if obj.sprite.image != self.animations[animation_name]:
                        obj.sprite.image = self.animations[animation_name]
                        obj.frame.new_image = obj.sprite.image

                        self.sfx['jump'].play()
                        self.setRunningSound(None)
                else:
                    self.jump_scheduled = False

                if obj.on_ladder and (not move_up and not move_down):
                    # switch sprite to ladder, still
                    if obj.sprite.image != self.animations['lem_climb_still']:
                        obj.sprite.image = self.animations['lem_climb_still']
                        obj.frame.new_image = obj.sprite.image

                        self.setRunningSound(None)



            # gravity
            gravity_accel = 800
            if not on_ground and not obj.on_ladder:
                obj.vel.y -= gravity_accel * dt

            # friction
            friction_accel = 380
            if on_ground:
                if abs(obj.vel.x) < abs(friction_accel * dt):
                    obj.vel.x = 0
                else:
                    obj.vel.x += friction_accel * dt * -sign(obj.vel.x)

            # conveyor belts
            max_conveyor_speed = 700
            if apply_belt_velocity > 0:
                if obj.vel.x + apply_belt_velocity > max_conveyor_speed:
                    obj.vel.x += max(max_conveyor_speed - obj.vel.x, 0)
                else:
                    obj.vel.x += apply_belt_velocity
            elif apply_belt_velocity < 0:
                if obj.vel.x + apply_belt_velocity < -max_conveyor_speed:
                    obj.vel.x += min(-max_conveyor_speed - obj.vel.x, 0)
                else:
                    obj.vel.x += apply_belt_velocity
            
            if (on_ground and obj.vel.get_length_sqrd() == 0) and obj.is_belly_flop:
                # replace tiles it took up with dead body
                self.setTile(block_at_feet+Vec2d(0, 1), self.tiles.enum.DeadBodyMiddle)
                self.setTile(block_at_feet+Vec2d(1, 1), self.tiles.enum.DeadBodyRight)
                self.setTile(block_at_feet+Vec2d(-1, 1), self.tiles.enum.DeadBodyLeft)
                
                obj.delete()

        if char is not None:
            char.frame.pos = char.pos
            char.frame.vel = char.vel
            char.frame.on_ladder = char.on_ladder

        # prepare sprites for drawing
        # physical objects
        for obj in self.physical_objects:
            if not obj.gone:
                try:
                    offset = self.animation_offset[obj.sprite.image]
                except KeyError:
                    offset = Vec2d(0, 0)
                pos = obj.pos + offset
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

        if self.control_lemming >= len(self.lemmings):
            return

        if control == Control.Explode:
            self.explode_queued = True
        elif control == Control.BellyFlop:
            if self.held_by is not None:
                self.bellyflop_queued = True
            else:
                char = self.lemmings[self.control_lemming]
                block_at_feet = (Vec2d(char.frame.pos.x + self.level.tilewidth / 2, char.frame.pos.y-1) / tile_size).do(int)
                on_ground = self.getBlockIsSolid(block_at_feet)

                if not on_ground:
                    self.bellyflop_queued = True
        elif control == Control.Freeze:
            self.freeze_queued = True


    def on_key_release(self, symbol, modifiers):
        try:
            self.control_state[self.controls[symbol]] = False
        except KeyError:
            pass

    def on_draw(self):
        self.game.window.clear()

        # far background
        far_bgpos = Vec2d(-((self.scroll.x * 0.25) % self.sprite_bg_left.width), -(self.scroll.y * 0.10))
        if far_bgpos.y > 0:
            far_bgpos.y = 0
        if far_bgpos.y + self.sprite_bg_left.height < self.game.window.height:
            far_bgpos.y = self.game.window.height - self.sprite_bg_left.height
        far_bgpos.do(int)
        pyglet.gl.glLoadIdentity()
        pyglet.gl.glTranslatef(far_bgpos.x, far_bgpos.y, 0.0)
        self.batch_bg2.draw()

        # close background
        close_bgpos = Vec2d(-((self.scroll.x * 0.5) % self.sprite_bg2_left.width), -(self.scroll.y * 0.20))
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

        # hud
        pyglet.gl.glLoadIdentity()
        self.batch_static.draw()
        if self.game.show_fps:
            self.fps_display.draw()

    def blockAt(self, abs_pt):
        return (abs_pt / tile_size).do(int)

    def getTile(self, block_pos, layer_index=0):
        try:
            return self.tiles.info[self.level.layers[layer_index].content2D[block_pos.x][block_pos.y]]
        except IndexError:
            return self.tiles.info[self.tiles.enum.Air]
        except KeyError:
            return self.tiles.info[self.tiles.enum.Air]

    def getBlockIsSolid(self, block_pos):
        tile_there = self.getTile(block_pos)
        if tile_there.solid:
            return True

        # check if there is an object filling this role
        for platform in self.platform_objects:
            if platform.solidAt(block_pos):
                return True

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
    
    def hitButtonId(self, button_id):
        try:
            responders = self.button_responders[button_id]
        except KeyError:
            return
        for responder in responders:
            responder.toggle()

    def load(self):
        global tile_size
        self.level = tiledtmxloader.TileMapParser().parse_decode_load(self.level_fd, tiledtmxloader.ImageLoaderPyglet())
        tile_size = Vec2d(self.level.tilewidth, self.level.tileheight)

        self.loadImages()
        self.loadSoundEffects()

        self.tiles = TileSet(self.level.tile_sets[0])


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
        self.obj_sprites = {}
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
                elif obj.type == 'Decoration':
                    if obj.properties.has_key('img'):
                        img = pyglet.resource.image(obj.properties['img'])
                    else:
                        img = self.animations[obj.properties['animation']]
                    self.obj_sprites[obj] = pyglet.sprite.Sprite(img,
                        x=obj.x, y=translate_y(obj.y, obj.height), batch=self.batch_level, group=group)
                elif obj.type == 'Agent':
                    try:
                        direction = int(obj.properties['direction'])
                    except KeyError:
                        direction = 1

                    pos = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    size = (Vec2d(obj.width, obj.height) / tile_size).do(int)
                    if obj.properties['type'] == 'monster':
                        try:
                            throw_vel = Vec2d(float(obj.properties['throw_vel_x']), float(obj.properties['throw_vel_y']))
                        except KeyError:
                            throw_vel = None
                        self.physical_objects.append(Monster(pos, size, group, self.batch_level, self, direction, throw_vel))
                    elif obj.properties['type'] == 'gunner':
                        self.physical_objects.append(Gunner(pos, size, group, self.batch_level, self))
                            
                elif obj.type == 'Bridge':
                    up_img = pyglet.resource.image(obj.properties['up_img'])
                    down_img = pyglet.resource.image(obj.properties['down_img'])
                    bridge_pos = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    bridge_pos_grid = (bridge_pos / tile_size).do(int)
                    bridge_size = (Vec2d(obj.width, obj.height) / tile_size).do(int)
                    bridge = Bridge(bridge_pos_grid, bridge_size, obj.properties['state'],
                        pyglet.sprite.Sprite(up_img, x=bridge_pos.x, y=bridge_pos.y, batch=self.batch_level, group=group),
                        pyglet.sprite.Sprite(down_img, x=bridge_pos.x, y=bridge_pos.y, batch=self.batch_level, group=group))
                    self.button_responders[obj.properties['button_id']] = bridge
                    self.platform_objects.append(bridge)
                elif obj.type == 'TrapDoor':
                    img = pyglet.resource.image(obj.properties['img'])
                    pos = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    pos_grid = (pos / tile_size).do(int)
                    size = (Vec2d(obj.width, obj.height) / tile_size).do(int)
                    self.button_responders[obj.properties['button_id']] = TrapDoor(pos_grid, size,
                        obj.properties['state'],
                        pyglet.sprite.Sprite(img, x=pos.x, y=pos.y, batch=self.batch_level, group=group))
                elif obj.type == 'Button':
                    up_img = pyglet.resource.image(obj.properties['up_img'])
                    down_img = pyglet.resource.image(obj.properties['down_img'])
                    button_pos = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    button_pos_grid = (button_pos / tile_size).do(int)
                    self.buttons[tuple(button_pos_grid)] = Button(button_pos_grid, obj.properties['button_id'],
                        pyglet.sprite.Sprite(up_img, x=button_pos.x, y=button_pos.y, batch=self.batch_level, group=group),
                        pyglet.sprite.Sprite(down_img, x=button_pos.x, y=button_pos.y, batch=self.batch_level, group=group),
                        float(obj.properties['delay']), self)
                elif obj.type == 'GearButton':
                    pos = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    size = (Vec2d(obj.width, obj.height) / tile_size).do(int)
                    pos_grid = (pos / tile_size).do(int)
                    gear = Gear(pos, size, obj.properties['button_id'], pyglet.sprite.Sprite(self.animations['gear_turning'],
                        x=pos.x, y=pos.y, batch=self.batch_level, group=group), self)
                    it = Vec2d(0, 0)
                    for it.x in range(pos_grid.x, pos_grid.x+size.x):
                        for it.y in range(pos_grid.y, pos_grid.y+size.y):
                            self.buttons[tuple(it)] = gear
                elif obj.type == 'Victory':
                    pos = (Vec2d(obj.x, translate_y(obj.y, obj.height)) / tile_size).do(int)
                    size = (Vec2d(obj.width, obj.height) / tile_size).do(int)
                    it = Vec2d(0, 0)
                    for it.y in range(pos.y, pos.y+size.y):
                        for it.x in range(pos.x, pos.x+size.x):
                            self.victory[tuple(it)] = True
                elif obj.type == 'ConveyorBelt':
                    pos = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    pos_grid = (pos / tile_size).do(int)
                    size = (Vec2d(obj.width, obj.height) / tile_size).do(int)
                    try:
                        state = obj.properties['state']
                    except KeyError:
                        state = 'on'
                    try:
                        direction = int(obj.properties['direction'])
                    except KeyError:
                        direction = 1
                    self.button_responders[obj.properties['button_id']] = ConveyorBelt(pos_grid, size, 
                        pyglet.sprite.Sprite(self.animations['belt_on'], x=pos.x, y=pos.y, group=group, batch=self.batch_level),
                        self, state=state, direction=direction)
                elif obj.type == 'BombSpawner':
                    pos = Vec2d(obj.x, translate_y(obj.y, obj.height))
                    size = Vec2d(obj.width, obj.height)
                    try:
                        state = obj.properties['state']
                    except KeyError:
                        state = 'on'
                    try:
                        delay = float(obj.properties['delay'])
                    except KeyError:
                        delay = 1
                    spawner = BombSpawner(pos, size, self, delay, state=state)
                    self.button_responders[obj.properties['button_id']] = spawner
                    

        if not had_start_point:
            assert False, "Level missing start point."

        if not had_player_layer:
            print("Level was missing PlayerLayer")
            self.group_char = pyglet.graphics.OrderedGroup(self.getNextGroupNum())
        self.group_fg = pyglet.graphics.OrderedGroup(self.getNextGroupNum())

        # load bg music
        try:
            bg_music_file = self.level.properties['bg_music']
        except KeyError:
            bg_music_file = None
        if bg_music_file is not None:
            self.bg_music = pyglet.resource.media(bg_music_file, streaming=True)
            self.bg_music_player.queue(self.bg_music)
            self.bg_music_player.play()

    def isVictory(self, block):
        return self.victory.has_key(tuple(block))

    def execute(self):
        self.createWindow()
        self.start()

        pyglet.app.run()

    def spawnBullet(self, pos, vel):
        self.physical_objects.append(Bullet(pos, vel, pyglet.sprite.Sprite(self.img_bullet,
            x=pos.x, y=pos.y, batch=self.batch_level, group=self.group_fg), self))

        self.sfx['gunshot'].play()

    def hitByBullet(self):
        self.explode_queued = True
        
    def spawnBomb(self, pos, vel, fuse):
        self.physical_objects.append(Bomb(pos, vel, fuse, pyglet.sprite.Sprite(self.img_bomb,
            x=pos.x, y=pos.y, batch=self.batch_level, group=self.group_fg), self))
