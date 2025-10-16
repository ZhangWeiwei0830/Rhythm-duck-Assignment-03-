Rhythm Duck — Pixel rhythm game demo

Repo name suggestion: rhythm-duck-demo

Description: A small pixel-art rhythm game demo written in Python and Pygame. Includes a recordable auto-demo, pixel UI, and three short levels. Use `111rhythm_duck_final.py` as the playable entrypoint; run with `--record` to generate a demo video in `recordings/`.

How to run locally

- Install dependencies (Python 3.9+):

  pip install pygame numpy imageio[ffmpeg]

- Run the game:

  python3 "111rhythm_duck_final.py"

- Record an automated demo video:

  python3 "111rhythm_duck_final.py" --record

Files of interest

- `111rhythm_duck_final.py` — main pixel game with recording support
- `111rhythm_duck.py` — earlier working copy
- `demo/` — demo launcher
- `recordings/` — generated demo frames and mp4 recordings

License

Place any license text here.
