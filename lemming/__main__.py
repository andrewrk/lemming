from __future__ import division, print_function, unicode_literals
range = xrange

from optparse import OptionParser
from game import Game
from leveleditor import LevelEditor

def main():
    parser = OptionParser("see --help for options")
    parser.add_option("-l", "--level", dest="level", help="level")

    options, args = parser.parse_args()
    options_dict = vars(options)
    
    if options_dict['level'] is not None:
        # load level from disk and go into level editor mode
        level_filename = options_dict['level']
        level_editor = LevelEditor()
        level_editor.loadLevel(level_filename)
        level_editor.execute()
    else:
        game = Game()
        game.execute()


