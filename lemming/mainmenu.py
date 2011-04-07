from __future__ import division, print_function, unicode_literals; range = xrange

from screen import Screen
import game

import pyglet

class MainMenu(Screen):
    def __init__(self, game):
        self.game = game

    def start(self):
        self.game.window.set_handler('on_draw', self.on_draw)
        self.game.window.set_handler('on_key_press', self.on_key_press)
        self.game.window.set_handler('on_key_release', self.on_key_release)

        pyglet.clock.schedule_interval(self.update, 1/game.target_fps)
        self.fps_display = pyglet.clock.ClockDisplay()

    def clear(self):
        self.game.window.remove_handlers()

    def handleNewGame(self):
        self.game.startPlaying()

    def handleContinue(self):
        self.game.load()
        self.game.startPlaying()

    def on_draw(self):
        self.game.window.clear()

        self.fps_display.draw()

    def update(self, dt):
        pass

    def on_key_press(self, symbol, modifiers):
        self.game.startPlaying()

    def on_key_release(self, symbol, modifiers):
        pass

