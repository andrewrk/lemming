from __future__ import division, print_function, unicode_literals; range = xrange

from screen import Screen
import game

import pyglet

from vec2d import Vec2d

class MainMenu(Screen):
    def __init__(self, game):
        self.game = game

        self.arrow_positions = (
            (Vec2d(149, 224), self.handleNewGame),
            (Vec2d(154, 125), self.handleContinue),
        )
        self.arrow_position = 0
        self.title_pos = Vec2d(46, 364)
        self.lem_pos = Vec2d(506, 0)

    def start(self):
        # load images
        img_bg = pyglet.resource.image('title/bg.png')
        img_title = pyglet.resource.image('title/title.png')
        img_continue = pyglet.resource.image('title/continue.png')
        img_new_game = pyglet.resource.image('title/new_game.png')
        img_arrow = pyglet.resource.image('title/arrow.png')
        img_lem = pyglet.resource.image('title/lem.png')

        # batches
        self.batch = pyglet.graphics.Batch()

        # groups
        group_bg = pyglet.graphics.OrderedGroup(0)
        group_fg = pyglet.graphics.OrderedGroup(1)

        # position sprites
        self.sprite_bg = pyglet.sprite.Sprite(img_bg, x=0, y=0, batch=self.batch, group=group_bg)
        self.sprite_title = pyglet.sprite.Sprite(img_title, x=self.title_pos.x, y=self.title_pos.y, batch=self.batch, group=group_fg)
        self.sprite_new_game = pyglet.sprite.Sprite(img_new_game,
            x=self.arrow_positions[0][0].x, y=self.arrow_positions[0][0].y, batch=self.batch, group=group_fg)
        self.sprite_continue = pyglet.sprite.Sprite(img_continue,
            x=self.arrow_positions[1][0].x, y=self.arrow_positions[1][0].y, batch=self.batch, group=group_fg)
        self.sprite_arrow = pyglet.sprite.Sprite(img_arrow, x=0, y=0, batch=self.batch, group=group_fg)
        self.sprite_lem = pyglet.sprite.Sprite(img_lem, x=self.lem_pos.x, y=self.lem_pos.y, batch=self.batch, group=group_fg)

        # load bg music
        self.bg_music_player = pyglet.media.Player()
        self.bg_music_player.eos_action = pyglet.media.Player.EOS_LOOP
        self.bg_music_player.volume = 0.50
        self.bg_music = pyglet.resource.media('music/depressing.mp3', streaming=True)
        self.bg_music_player.queue(self.bg_music)
        self.bg_music_player.play()

        # set up handlers
        self.game.window.set_handler('on_draw', self.on_draw)
        self.game.window.set_handler('on_key_press', self.on_key_press)

        pyglet.clock.schedule_interval(self.update, 1/game.target_fps)
        self.fps_display = pyglet.clock.ClockDisplay()

    def clear(self):
        self.game.window.remove_handlers()
        pyglet.clock.unschedule(self.update)

        self.bg_music_player.pause()
        self.bg_music_player = None

    def handleNewGame(self):
        self.game.startPlaying()

    def handleContinue(self):
        self.game.load()
        self.game.startPlaying()

    def on_draw(self):
        self.game.window.clear()
        self.batch.draw()
        self.fps_display.draw()

    def update(self, dt):
        self.sprite_arrow.set_position(*(self.arrow_positions[self.arrow_position][0] + Vec2d(-44, 0)))

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.UP:
            self.arrow_position = (self.arrow_position - 1) % 2
        elif symbol == pyglet.window.key.DOWN:
            self.arrow_position = (self.arrow_position + 1) % 2
        elif symbol == pyglet.window.key.SPACE or symbol == pyglet.window.key.ENTER:
            self.arrow_positions[self.arrow_position][1]()

