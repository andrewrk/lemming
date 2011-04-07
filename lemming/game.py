from __future__ import division, print_function, unicode_literals; range = xrange

import pyglet

import mainmenu
import levelplayer
import os

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
        self.save_filename = os.path.join(pyglet.resource.get_script_home(), 'save_game')

    def load(self):
        try:
            with open(self.save_filename, 'r') as fd:
                self.current_level = int(fd.read())
        except IOError:
            self.current_level = 0
        except ValueError:
            self.current_level = 0
    
    def save(self):
        try:
            with open(self.save_filename, 'w') as fd:
                fd.write(str(self.current_level))
        except IOError:
            print("Unable to save game, IOError")

    def gotoNextLevel(self):
        if self.level_filename is not None:
            self.startPlaying()
            return

        self.clearCurrentScreen()
        self.current_level += 1
        self.save()
        if self.current_level == len(levels):
            self.current_screen = WinScreen(self)
        else:
            self.current_screen = levelplayer.LevelPlayer(self, pyglet.resource.file(levels[self.current_level]))
        self.current_screen.start()

    def startPlaying(self):
        self.clearCurrentScreen()
        if self.level_filename is None:
            self.current_screen = levelplayer.LevelPlayer(self, pyglet.resource.file(levels[self.current_level]))
        else:
            self.current_screen = levelplayer.LevelPlayer(self, open(self.level_filename, 'rb'))
        self.current_screen.start()

    def start(self, level_filename=None):
        self.window = pyglet.window.Window(width=853, height=480)
        self.level_filename = level_filename
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
        self.startPlaying()

