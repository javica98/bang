This directory contains a copy of the pygame_cards package (from Downloads) used as a UI base.

Notes:
- The original package targets Python 2. The code here has minimal fixes for Python 3 (print statements and
  a few type checks) but may still require deeper porting (e.g., metaclass syntax, basestring uses, division semantics).
- Image assets are not copied. The original images are located at:
  C:\Users\Asus\Downloads\pygame_cards-0.1\pygame_cards-0.1\pygame_cards\img\
  You can either copy the `img/` folder into this package or update `card_json` paths to point to that location.

Next steps:
- Decide if you want me to fully port the package to Python 3 and copy images into the project.
- Or, I can write an adapter module that maps `Carta`/`Jugador` to the Pygame UI using these classes.
