Rhythm Duck — Pixel rhythm game demo

Repo name suggestion: rhythm-duck-demo

Description: A small pixel-art rhythm game demo written in Python and Pygame. Includes a recordable auto-demo, pixel UI, and three short levels. Use `111rhythm_duck_final.py` as the playable entrypoint; run with `--record` to generate a demo video in `recordings/`.

How to run locally

- Create and activate a virtual environment, install pinned dependencies, then run:

  python3 -m venv venv
  source venv/bin/activate     # Windows: venv\Scripts\activate
  pip install -r requirements.txt
  python rhythm_duck.py        # your main file (rename if needed)

- To record an automated demo (auto-play):

  python3 "111rhythm_duck_final.py" --record

Files of interest

- `111rhythm_duck_final.py` — main pixel game with recording support
- `111rhythm_duck.py` — earlier working copy
- `demo/` — demo launcher
- `recordings/` — generated demo frames and mp4 recordings

License

Place any license text here.

Controls (简明版)

- W / S 或 ↑ / ↓ : 上下换轨
- Space / Delete : 开始、重试、返回关卡选择
- MUSIC 按钮 : 静音 / 开声
- ☀ / ☁ : 切换音符样式
- ⏏ : 退出当前关卡回 Level Select
- 通关后 : 解锁下一个关卡，可点击 Home / Next
- 失败判定 : 漏吃 10 颗 或 右侧 10 格血条 ≤2 时闪红（失败）
