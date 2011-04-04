from __future__ import division, print_function, unicode_literals
range = xrange

from optparse import OptionParser
from game import Game

def main():
    parser = OptionParser("see --help for options")
    parser.add_option("-l", "--level", dest="level", help="level")
    parser.add_option('-n', '--novbo', action='store_true', help='Disable the use of VBOs (buggy/slow on some drivers)', default=False)

    options, args = parser.parse_args()

    if options.novbo:
        # monkey-patch pyglet (thanks muave http://code.google.com/p/bamboo-warrior/source/browse/trunk/run_game.py)
        from pyglet.graphics import vertexdomain
        default_create_attribute_usage = vertexdomain.create_attribute_usage
        def create_attribute_usage(format):
                attribute, usage, vbo = default_create_attribute_usage(format)
                return attribute, usage, False
        vertexdomain.create_attribute_usage = create_attribute_usage
    
    if options.level:
        game = Game()
        game.load(options.level)
        game.execute()
    else:
        print("must supply a level for now with -l")

