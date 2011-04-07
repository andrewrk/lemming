from __future__ import division, print_function, unicode_literals; range = xrange

import pyglet

import mainmenu
import levelplayer

levels = [
    'level1.tmx',
    'level2.tmx',
]

target_fps = 60

class Game(object):
    def __init__(self, width=853, height=480, show_fps=False):
        self.current_level = 0
        self.current_screen = None
        self.window = None
        self.width = width
        self.height = height
        self.show_fps = show_fps

    def load(self):
        with open('save_game', 'rb') as fd:
            self.current_level = int(fd.read())
    
    def save(self):
        with open('save_game', 'rb') as fd:
            fd.write(self.current_level)

    def gotoNextLevel(self):
        self.clearCurrentScreen()
        self.current_level += 1
        if self.current_level == len(levels):
            self.current_screen = WinScreen(self)
        else:
            self.current_screen = levelplayer.LevelPlayer(self, pyglet.resource.file(levels[self.current_level]))
        self.current_screen.start()

    def startPlaying(self):
        self.clearCurrentScreen()
        self.current_screen = levelplayer.LevelPlayer(self, pyglet.resource.file(levels[self.current_level]))
        self.current_screen.start()

    def start(self, level_filename=None):
        self.window = pyglet.window.Window(width=853, height=480)
        if level_filename is None:
            self.current_screen = mainmenu.MainMenu(self)
            self.current_screen.start()
        else:
            self.current_screen = levelplayer.LevelPlayer(self, open(level_filename, 'rb'))
            self.current_screen.start()
        pyglet.app.run()

    def clearCurrentScreen(self):
        if self.current_screen is not None:
            self.current_screen.clear()

    def restartLevel(self):
        print("restarting level")
        self.startPlaying()
