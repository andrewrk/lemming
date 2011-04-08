from __future__ import division, print_function, unicode_literals; range = xrange

import pyglet

import mainmenu
import levelplayer
import winscreen
import os

levels = [
    'level1.tmx',
    'level2.tmx',
]

target_fps = 60

# add data folder to pyglet resource path
_this_py = os.path.abspath(os.path.dirname(__file__))
_data_dir = os.path.normpath(os.path.join(_this_py, '..', 'data'))
pyglet.resource.path = [_data_dir, 'data']
pyglet.resource.reindex()

# monkey patch pyglet to fix a resource loading bug
slash_paths = filter(lambda x: x.startswith('/'), pyglet.resource._default_loader._index.keys())
for path in slash_paths:
    pyglet.resource._default_loader._index[path[1:]] = pyglet.resource._default_loader._index[path]


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
        self.setScreenToCurrentLevel()
        self.current_screen.start()

    def setScreenToCurrentLevel(self):
        if self.current_level == len(levels):
            self.current_screen = winscreen.WinScreen(self)
        else:
            self.current_screen = levelplayer.LevelPlayer(self, pyglet.resource.file(levels[self.current_level]))

    def startPlaying(self):
        self.clearCurrentScreen()
        if self.level_filename is None:
            self.setScreenToCurrentLevel()
        else:
            self.current_screen = levelplayer.LevelPlayer(self, open(self.level_filename, 'rb'))
        self.current_screen.start()

    def start(self, level_filename=None):
        self.window = pyglet.window.Window(width=self.width, height=self.height, caption="Lemming")
        self.window.set_icon(pyglet.resource.image('icon.png'))
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

