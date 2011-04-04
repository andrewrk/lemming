from __future__ import division, print_function, unicode_literals
range = xrange

from optparse import OptionParser
from game import Game
from leveleditor import LevelEditor

def main():
    parser = OptionParser("see --help for options")
    parser.add_option("-l", "--level", dest="level", help="level")
    parser.add_option('-n', '--novbo', action='store_true', help='Disable the use of VBOs (buggy/slow on some drivers)', default=False)

    options, args = parser.parse_args()
    options_dict = vars(options)

    if options.novbo:
        # monkey-patch pyglet (thanks muave http://code.google.com/p/bamboo-warrior/source/browse/trunk/run_game.py)
        from pyglet.graphics import vertexdomain
        default_create_attribute_usage = vertexdomain.create_attribute_usage
        def create_attribute_usage(format):
                attribute, usage, vbo = default_create_attribute_usage(format)
                return attribute, usage, False
        vertexdomain.create_attribute_usage = create_attribute_usage
    
    if options_dict['level'] is not None:
        # load level from disk and go into level editor mode
        level_filename = options_dict['level']
        level_editor = LevelEditor(level_filename)
        level_editor.execute()
    else:
        game = Game()
        game.execute()


