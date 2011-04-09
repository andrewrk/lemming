Your Game Title


Entry in PyWeek #12  <http://www.pyweek.org/12/>
URL: http://pyweek.org/e/lemming
Team: Superjoe Software
Members: Andrew Kelley
License: see LICENSE.txt
Special Thanks: Tyler Heald for the Factory bg music and credits song.


Running the Game
----------------

On Windows or Mac OS X, locate the "run_game.pyw" file and double-click it.

Othewise open a terminal / console and "cd" to the game directory and run:

  python run_game.py


How to Play the Game
--------------------

Use the in-game text to help you learn.
Arrow keys: move
1:          belly flop
2:          explode

This is explained in-game.

IF THE GAME CRASHES or becomes slow, restart the program and hit continue.

Development notes 
-----------------

Creating a source distribution with::

   python setup.py sdist

You may also generate Windows executables and OS X applications::

   python setup.py py2exe
   python setup.py py2app

Upload files to PyWeek with::

   python pyweek_upload.py

Upload to the Python Package Index with::

   python setup.py register
   python setup.py sdist upload

