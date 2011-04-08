from __future__ import division, print_function, unicode_literals; range = xrange

from screen import Screen

import pyglet
from vec2d import Vec2d

class WinScreen(Screen):
    def __init__(self, game):
        self.game = game

    def start(self):
        self.sprite_bg = pyglet.sprite.Sprite(pyglet.resource.image('credits/bg.png'), x=0, y=0)

        self.bg_music_player = pyglet.media.Player()
        self.bg_music_player.eos_action = pyglet.media.Player.EOS_LOOP
        self.bg_music_player.volume = 0.50
        self.bg_music = pyglet.resource.media('music/glitch.mp3', streaming=True)
        self.bg_music_player.queue(self.bg_music)
        self.bg_music_player.play()

        self.game.window.set_handler('on_draw', self.on_draw)

        self.fps_display = pyglet.clock.ClockDisplay()

    def clear(self):
        self.game.window.remove_handlers()
        self.bg_music_player.pause()
        self.bg_music_player = None
        self.sprite_bg = None

    def on_draw(self):
        self.game.window.clear()

        self.sprite_bg.draw()

        if self.game.show_fps:
            self.fps_display.draw()

