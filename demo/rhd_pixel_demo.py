# Demo launcher copy of rhythm_duck_pixel_v3.py
# Run this file to start the pixel demo.

import sys, os
# Ensure pygame finds fonts etc when run from demo folder
here = os.path.dirname(__file__)
proj_root = os.path.abspath(os.path.join(here, '..'))
sys.path.insert(0, proj_root)

# Import the demo module code by executing the original file
with open(os.path.join(proj_root, 'rhythm_duck_pixel_v3.py'), 'r', encoding='utf-8') as f:
    code = f.read()
exec(compile(code, os.path.join(proj_root, 'rhythm_duck_pixel_v3.py'), 'exec'), globals())
