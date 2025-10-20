import sys, math, os, subprocess, time
import pygame
import numpy as np

# ================= Pixel canvas (NEAREST ONLY) =================
SCREEN_W, SCREEN_H = 960, 600
PX_W, PX_H = 240, 150
SCALE = SCREEN_W // PX_W
assert SCREEN_W % PX_W == 0 and SCREEN_H % PX_H == 0

# ---- Colors ----
C_BG   = (173,216,230)
C_CITY = (130,170,190)
C_LINE = (120,170,210)   # lane (thicker than note)
C_DUCK = (252,202, 62)
C_BEAK = (255,120, 60)
C_EYE  = (255,255,255)
C_NOTE = (255,234,120)
C_MISS = (150,160,170)
C_INFO = ( 30, 40, 60)

# ---- Gameplay ----
HIT_X    = 40
NOTE_SPD = 70
NOTE_H   = 5
LANE_THK = NOTE_H + 2
HIT_WIN  = 6
MOUTH_T  = 0.15

HP_SEGMENTS    = 10
# A miss reduces 2 HP segments. We'll use miss_count (per-note misses).
# Assumption: thresholds are mapped as follows (per your spec):
# 0 misses -> 3 stars
# 1 miss  -> 2 stars (HP 8)
# 2-3 misses -> 1 star (HP 6 or 4) — user spec was ambiguous for 2 misses, we treat 2 as 1 star
# 4+ misses -> fail (no pass). Mid-game HP <= 0 also triggers fail.
MAX_MISSES = 4

# ---- Audio ----
SR    = 44100
VOL   = 0.9

# Lightweight config to avoid scattering globals
class GameConfig:
    def __init__(self):
        self.muted = False
        self.note_style = "sun"

GAME_CFG = GameConfig()

def square_sound(freq=440, length=0.24, vol=1.0):
    n = int(length*SR)
    t = np.linspace(0,length,n,endpoint=False)
    w = np.sign(np.sin(2*np.pi*freq*t)).astype(np.float32)
    a = int(0.006*SR); r=int(0.04*SR)
    env = np.ones(n, np.float32)
    if a>0: env[:a]=np.linspace(0,1,a,endpoint=False)
    if r>0: env[-r:]=np.linspace(1,0.001,r)
    w*=env*vol
    arr=(w*32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.stack([arr,arr],axis=1))

def noise_click(length=0.06, vol=0.45):
    n=int(length*SR); w=(np.random.randn(n).astype(np.float32))
    env=np.linspace(1,0.001,n)
    arr=(w*env*vol*32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.stack([arr,arr],axis=1))

def midi_to_hz(m): return 440.0*(2**((m-69)/12))
def bg_song_twinkle(bpm=100):
    notes=[60,60,67,67,69,69,67, 65,65,64,64,62,62,60]
    lens =[1]*6+[2] + [1]*6+[2]
    beat=60.0/bpm
    parts=[]
    for m,l in zip(notes,lens):
        d=l*beat; n=int(d*SR); t=np.linspace(0,d,n,endpoint=False)
        w=np.sign(np.sin(2*np.pi*midi_to_hz(m)*t)).astype(np.float32)
        a=int(0.006*SR); r=int(0.04*SR)
        env=np.ones(n,np.float32)
        if a>0: env[:a]=np.linspace(0,1,a,endpoint=False)
        if r>0: env[-r:]=np.linspace(1,0.001,r)
        parts.append(w*env*0.35)
    mono=np.concatenate(parts)
    arr=(mono*32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.stack([arr,arr],axis=1))

LANE_FREQS = [261.63, 329.63, 392.00]

# ---- Levels (no same-tick multi-lane) ----
LEVELS = [
    dict(name="Lv1", bpm=92,  lanes=2, pattern=[
        (0,0),(1,0),(2,1),(3,1),(4,0),(5,1),(6,0),(7,1),
    ]),
    dict(name="Lv2", bpm=108, lanes=3, pattern=[
        (0,0),(1,1),(2,2),(3,1),(4,0),(5,1),(6,2),(7,1),
        (8,0),(9,1),(10,2),(11,1),
    ]),
    dict(name="Lv3", bpm=122, lanes=4, pattern=[
        (0,0),(0.75,1),(1.5,2),(2.25,1),
        (3.0,0),(3.75,1),(4.5,2),(5.25,1),
        (6.0,2),(6.75,1),(7.5,0),(8.25,1),
    ]),
]

# ================= Pixel helpers =================
def px_rect(s, x,y,w,h,c): s.fill(c, pygame.Rect(x,y,w,h))

def px_text(s, text, x, y, color=C_INFO, size=12, outline=False):
    # tiny crisp monospace; render ONLY on pixel canvas, antialias=False
    # use a slightly larger monospaced font to ensure visibility after scaling
    # robust font rendering: try multiple fonts and verify rendered surface is non-empty
    def render_with_fallback(t, size=12, bold=True, color=color):
        has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in t)
        # candidate font names (macOS common + generic fallbacks)
        if has_cjk:
            candidates = ["PingFang TC", "PingFang SC", "Heiti TC", "Heiti SC", "Hiragino Kaku Gothic ProN", "Noto Sans CJK SC", None]
            size = max(size, 13)
        else:
            candidates = ["Courier New", "Menlo", None]
        for name in candidates:
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
            except Exception:
                try:
                    f = pygame.font.SysFont(None, size, bold=bold)
                except Exception:
                    continue
            try:
                img = f.render(t, True, color)
            except Exception:
                continue
            # ensure rendered image is not empty (some fonts may produce blank glyphs)
            if img.get_bounding_rect().width > 0:
                return img
        # last resort: default font render (may be empty)
        return pygame.font.SysFont(None, size, bold=bold).render(t, True, color)

    if outline:
        shadow = render_with_fallback(text, size=size, color=(10,10,10))
        s.blit(shadow, (x-1, y-1))
    img = render_with_fallback(text, size=size, color=color)
    s.blit(img, (x,y))

def px_text_center(s, text, cx, cy, color=C_INFO, size=12, outline=False):
    # render and center text on the pixel canvas
    # use the same robust renderer as px_text but centered
    def render_center_with_fallback(t, size=12, bold=True, color=color):
        has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in t)
        if has_cjk:
            candidates = ["PingFang TC", "PingFang SC", "Heiti TC", "Heiti SC", "Hiragino Kaku Gothic ProN", "Noto Sans CJK SC", None]
            size = max(size, 13)
        else:
            candidates = ["Courier New", "Menlo", None]
        for name in candidates:
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
            except Exception:
                try:
                    f = pygame.font.SysFont(None, size, bold=bold)
                except Exception:
                    continue
            try:
                img = f.render(t, True, color)
            except Exception:
                continue
            if img.get_bounding_rect().width > 0:
                return img
        return pygame.font.SysFont(None, size, bold=bold).render(t, True, color)

    if outline:
        shadow = render_center_with_fallback(text, size=size, color=(10,10,10))
        r = shadow.get_rect(); r.center=(cx-1, cy-1); s.blit(shadow, r)
    img = render_center_with_fallback(text, size=size, color=color)
    rect = img.get_rect()
    rect.center = (cx, cy)
    s.blit(img, rect)

def draw_bg(s, laneYs):
    s.fill(C_BG)
    px_rect(s, 0, PX_H-20, PX_W, 20, C_CITY)
    for y in laneYs:
        px_rect(s, 0, y-LANE_THK//2, PX_W, LANE_THK, C_LINE)
    # draw a semi-transparent blue zone left of the hit line (50% alpha)
    zone_h = (laneYs[-1] - laneYs[0]) + 16
    zone_surf = pygame.Surface((HIT_X, zone_h), pygame.SRCALPHA)
    zone_surf.fill((60,110,155,128))
    s.blit(zone_surf, (0, laneYs[0]-8))

# ---- Bigger pixel duck (~1.6x) ----
def draw_duck(s, x, y, mouth=False):
    # body
    px_rect(s, x-9, y-6, 16, 12, C_DUCK)
    px_rect(s, x+7, y-4,  6,  6, C_DUCK)
    px_rect(s, x-6, y+6,  6,  4, C_DUCK)
    # eye
    px_rect(s, x+10, y-4, 3, 3, C_EYE)
    # beak
    px_rect(s, x+13, y-2, 6 if mouth else 3, 3, C_BEAK)

# ---- Notes: sun / cloud ----
def draw_sun(s, cx, cy, miss=False):
    c = C_MISS if miss else C_NOTE
    px_rect(s, cx-2, cy-2, 5, 5, c)
    px_rect(s, cx-4, cy,   9, 1, c)
    px_rect(s, cx,   cy-4, 1, 9, c)

def draw_cloud(s, cx, cy, miss=False):
    c = C_MISS if miss else C_NOTE
    px_rect(s, cx-5, cy-2, 4, 3, c)
    px_rect(s, cx-1, cy-3, 4, 4, c)
    px_rect(s, cx+4, cy-2, 4, 3, c)

def draw_note(s, x,y, miss=False):
    (draw_cloud if GAME_CFG.note_style=="cloud" else draw_sun)(s, int(x), int(y), miss)

# ---- Pixel buttons (graphics only, no unicode) ----
def btn_box(s, r, active=True): px_rect(s, r.x, r.y, r.w, r.h, (230,230,230) if active else (180,180,180))
def btn_play(s, r):   # ▶ centered, smaller
    btn_box(s, r)
    cx,cy = r.x + r.w//2, r.y + r.h//2
    size = min(r.w, r.h) - 6
    pts = [(cx - size//3, cy - size//2), (cx - size//3, cy + size//2), (cx + size//2, cy)]
    pygame.draw.polygon(s, (20,20,20), pts)

def btn_speaker(s, r, muted=False):
    btn_box(s, r)
    cx,cy = r.x + r.w//2, r.y + r.h//2
    # small speaker body
    px_rect(s, cx-4, cy-2, 4, 4, (20,20,20))
    px_rect(s, cx-1, cy-3, 3, 6, (20,20,20))
    if muted:
        pygame.draw.line(s, (20,20,20), (cx+3,cy-3), (cx+6,cy+3), 1)
        pygame.draw.line(s, (20,20,20), (cx+6,cy-3), (cx+3,cy+3), 1)
    else:
        pygame.draw.line(s, (20,20,20), (cx+3,cy-2), (cx+6,cy-4), 1)
        pygame.draw.line(s, (20,20,20), (cx+3,cy+2), (cx+7,cy+2), 1)

def btn_style(s, r):
    btn_box(s, r)
    draw_note(s, r.x + r.w//2, r.y + r.h//2, miss=False)
def btn_style_toggle(s, r):
    # same as btn_style but named for toggle semantics in UI
    btn_box(s, r)
    draw_note(s, r.x + r.w//2, r.y + r.h//2, miss=False)
def btn_eject(s, r):  # ⏏ centered
    btn_box(s, r)
    cx,cy = r.x + r.w//2, r.y + r.h//2
    size = min(r.w, r.h) - 6
    pygame.draw.polygon(s, (20,20,20), [(cx-size//2, cy+size//4), (cx, cy-size//4), (cx+size//2, cy+size//4)])
    px_rect(s, cx-size//2, cy+size//4+3, size, 2, (20,20,20))

def btn_home(s, r):   # back arrow (left-pointing triangle) to match "返回"
    btn_box(s, r)
    cx,cy = r.x + r.w//2, r.y + r.h//2
    size = max(8, min(r.w, r.h) - 8)
    pts = [(cx + size//4, cy - size//3), (cx + size//4, cy + size//3), (cx - size//3, cy)]
    pygame.draw.polygon(s, (20,20,20), pts)

def btn_next(s, r, active=True):
    btn_box(s, r, active)
    cx,cy = r.x + r.w//2, r.y + r.h//2
    size = max(6, min(r.w, r.h) - 10)
    col=(20,20,20) if active else (100,100,100)
    pts = [(cx - size//4, cy - size//3), (cx - size//4, cy + size//3), (cx + size//3, cy)]
    pygame.draw.polygon(s, col, pts)

# ================= Entities =================
class Note:
    def __init__(self, x, lane, y):
        self.x=x; self.lane=lane; self.y=y
        self.hit=False; self.missed=False
    def update(self, dt):
        self.x -= NOTE_SPD*dt
        if not self.hit and not self.missed and self.x < HIT_X - HIT_WIN:
            self.missed=True
    def draw(self, s): draw_note(s, self.x, self.y, self.missed)

class Duck:
    def __init__(self, laneYs):
        self.lanes=laneYs; self.idx=min(1,len(laneYs)-1)
        self.y=self.lanes[self.idx]; self.mouth=0.0
    def set_lanes(self, laneYs):
        self.lanes=laneYs; self.idx=min(self.idx,len(laneYs)-1); self.y=self.lanes[self.idx]
    def up(self):   self.idx=max(0,self.idx-1); self.y=self.lanes[self.idx]
    def down(self): self.idx=min(len(self.lanes)-1,self.idx+1); self.y=self.lanes[self.idx]
    def eat(self):  self.mouth=MOUTH_T
    def update(self, dt):
        if self.mouth>0: self.mouth -= dt
    def draw(self, s): draw_duck(s, HIT_X-6, int(self.y), mouth=(self.mouth>0))

# ================= Scheduling =================
def lane_ys_for(n):
    if n == 2:
        return [60,90]
    if n == 3:
        return [50,80,110]
    # 4 lanes layout (evenly spaced)
    if n == 4:
        return [40,65,90,115]
    return [50,80,110]

def build_schedule(level):
    """
    把节拍量化到 tick（避免浮点比较误差），并强制同一时间只生成一颗音符。
    如果同一拍（或过近）出现多个音符，就把后面的顺延 1 个 tick。
    """
    TICKS = 8          # 每拍切成 8 份（八分音符精度）；可改为 12/16 提高精度
    MIN_GAP = 1        # 最小间隔：至少错开 1 个 tick；想更宽松可设为 2
    MIN_TIME_GAP = 0.5 # 最小时间间隔（秒）：保证任意两颗音符 spawn 时间相隔至少 0.5s

    bpm = level["bpm"]
    beat_sec = 60.0 / bpm

    # 计算从屏幕右侧到判定线的飞行时间（用于将“命中时间”换算成“生成时间”）
    start_x = PX_W + 12
    travel_time = (start_x - HIT_X) / NOTE_SPD

    used_ticks = set()
    last_tick  = -10**9
    last_spawn = -1e9
    schedule   = []

    # 先按 beat 排序，逐个处理
    for beat_pos, lane in sorted(level["pattern"], key=lambda x: x[0]):
        tick = int(round(beat_pos * TICKS))

        # 若该 tick 已被占用，或与上一颗太近，则顺延（保证不会同拍落两轨）
        while tick in used_ticks or tick <= last_tick + (MIN_GAP - 1):
            tick += 1

        # 计算 spawn_time，并保证与上一个 spawn 至少间隔 MIN_TIME_GAP
        hit_time = (tick / TICKS) * beat_sec
        spawn_time = max(0.0, hit_time - travel_time)
        while spawn_time - last_spawn < MIN_TIME_GAP:
            tick += 1
            # avoid collisions on ticks as well
            while tick in used_ticks:
                tick += 1
            hit_time = (tick / TICKS) * beat_sec
            spawn_time = max(0.0, hit_time - travel_time)

        used_ticks.add(tick)
        last_tick = tick
        last_spawn = spawn_time

        schedule.append({"spawn": spawn_time, "lane": lane})

    # 已按顺序生成；返回给主循环使用
    return schedule

# ----------------- Scoring -----------------
def score_for_hit(offset):
    """Return score label and points based on timing offset (seconds)."""
    a = abs(offset)
    if a <= 0.05:
        return "Perfect", 300
    if a <= 0.12:
        return "Great", 150
    if a <= 0.25:
        return "Good", 80
    return "OK", 30

def load_best_score():
    try:
        with open('best_score.txt','r') as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0

def save_best_score(v):
    try:
        with open('best_score.txt','w') as f:
            f.write(str(int(v)))
    except Exception:
        pass

# ================= Main =================
def main():
    global GAME_CFG
    # replace globals with config usage
    global GAME_CFG
    # command-line flags
    record_mode = ('--record' in sys.argv) or ('--auto-record' in sys.argv)
    frames_dir = None
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=1024)
    pygame.init(); pygame.font.init()
    screen=pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Rhythm Duck – PFAD A3")
    clock=pygame.time.Clock()
    px=pygame.Surface((PX_W,PX_H)).convert()

    if record_mode:
        ts = time.strftime('%Y%m%d_%H%M%S')
        out_root = os.path.join(os.getcwd(), 'recordings')
        os.makedirs(out_root, exist_ok=True)
        frames_dir = os.path.join(out_root, f'rhythm_duck_demo_{ts}')
        os.makedirs(frames_dir, exist_ok=True)
        print('Recording frames to', frames_dir)
        frames_muxed = False
        # used to ensure frames finished writing before mux
        frames_last_count = 0
        frames_last_stable_since = None

    lane_sounds=[square_sound(f,0.24,VOL) for f in LANE_FREQS]
    sfx_eat=noise_click(0.05,0.45)

    bg_ch=pygame.mixer.Channel(0)
    def play_bg(bpm):
        snd=bg_song_twinkle(bpm)
        if not GAME_CFG.muted: bg_ch.play(snd, loops=-1)
        else: bg_ch.stop()

    state="menu"; unlocked=1; level_idx=0
    lvl=LEVELS[level_idx]; laneYs=lane_ys_for(lvl["lanes"])
    duck=Duck(laneYs)

    # scoring
    score = 0
    last_hit_label = None
    best_score = load_best_score()

    miss_count=0; t=0.0; upcoming=[]; notes=[]; flash_t=0.0

    def start_level(i):
        nonlocal lvl, laneYs, t, upcoming, notes, miss_count, score, last_hit_label
        lvl = LEVELS[i]
        laneYs = lane_ys_for(lvl["lanes"])
        duck.set_lanes(laneYs)
        miss_count = 0
        t = 0.0
        notes = []
        upcoming = build_schedule(lvl)
        play_bg(lvl["bpm"])
        score = 0
        last_hit_label = None

    # Pixel buttons (no unicode)
    r_style = pygame.Rect(PX_W-36, 4, 14, 12)
    r_music = pygame.Rect(PX_W-18, 4, 14, 12)
    r_start = pygame.Rect(PX_W//2-7, PX_H//2+6, 14, 12)
    r_exit  = pygame.Rect(PX_W-18, PX_H-16, 14, 12)
    r_retry = pygame.Rect(PX_W//2-28, PX_H//2+8, 56, 12)
    # slightly larger pass buttons to avoid clipping
    r_pass_home = pygame.Rect(PX_W//2-56, PX_H//2+6, 52, 18)
    r_pass_next = pygame.Rect(PX_W//2+4, PX_H//2+6, 52, 18)

    while True:
        dt = clock.tick(60)/1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT: pygame.quit(); sys.exit(0)
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q): pygame.quit(); sys.exit(0)
                if e.key == pygame.K_m:
                    GAME_CFG.muted = not GAME_CFG.muted
                    if GAME_CFG.muted: bg_ch.stop()
                    else: play_bg(lvl["bpm"])
                if e.key == pygame.K_RETURN:
                    # Enter/Return also retries when failing
                    if state == "fail":
                        start_level(level_idx); state = "playing"

                if state in ("menu","select","fail","pass"):
                    if e.key in (pygame.K_SPACE, pygame.K_DELETE):
                        if state=="menu": state="select"
                        elif state=="select": start_level(level_idx); state="playing"
                        elif state=="fail": start_level(level_idx); state="playing"
                        elif state=="pass": state="select"

                if state=="playing":
                    if e.key in (pygame.K_w, pygame.K_UP): duck.up()
                    if e.key in (pygame.K_s, pygame.K_DOWN): duck.down()

            if e.type == pygame.MOUSEBUTTONDOWN:
                mx,my = pygame.mouse.get_pos(); mx//=SCALE; my//=SCALE
                if r_music.collidepoint(mx,my):
                    GAME_CFG.muted = not GAME_CFG.muted
                    if GAME_CFG.muted: bg_ch.stop()
                    else: play_bg(lvl["bpm"])
                elif r_style.collidepoint(mx,my):
                    GAME_CFG.note_style = "cloud" if GAME_CFG.note_style=="sun" else "sun"
                elif state=="menu" and r_start.collidepoint(mx,my):
                    state="select"
                elif state=="playing" and r_exit.collidepoint(mx,my):
                    state="select"; bg_ch.stop()
                elif state=="fail" and r_retry.collidepoint(mx,my):
                    start_level(level_idx); state = "playing"
                elif state=="pass":
                    # pass-screen buttons: home or next
                    if r_pass_home.collidepoint(mx,my):
                        state = "menu"
                    elif r_pass_next.collidepoint(mx,my):
                        if level_idx < len(LEVELS)-1:
                            level_idx += 1
                            start_level(level_idx)
                            state = "playing"

        # ===== Update =====
        if state=="playing":
            t += dt

            # spawn scheduled notes
            while upcoming and upcoming[0]["spawn"] <= t:
                info = upcoming.pop(0)
                notes.append(Note(PX_W+10, info["lane"], laneYs[info["lane"]]))

            for n in notes:
                n.update(dt)

            # auto-play: if recording, perform perfect hits when notes enter hit window
            if record_mode:
                for n in notes:
                    if not n.hit and not n.missed and abs(n.x - HIT_X) <= HIT_WIN:
                        # snap duck to lane and register hit
                        duck.idx = n.lane
                        duck.y = duck.lanes[duck.idx]
                        n.hit = True
                        duck.eat()
                        if not GAME_CFG.muted:
                            lane_sounds[min(n.lane,2)].play(); sfx_eat.play()
                        # scoring for auto-hit: assume perfect (offset ~=0)
                        label, pts = score_for_hit(0.0)
                        score += pts
                        last_hit_label = label

            # player input hit detection
            for n in notes:
                if not n.hit and not n.missed and n.lane==duck.idx and abs(n.x-HIT_X)<=HIT_WIN:
                    n.hit=True; duck.eat()
                    # compute timing offset based on x distance
                    offset = (n.x - HIT_X) / NOTE_SPD
                    label, pts = score_for_hit(offset)
                    score += pts
                    last_hit_label = label
                    if not GAME_CFG.muted:
                        lane_sounds[min(n.lane,2)].play(); sfx_eat.play()

            # process misses
            for n in notes:
                if n.missed:
                    miss_count += 1
                    # each miss reduces HP segments by 2
                    score = max(0, score-50)
                    n.missed=False

            notes = [n for n in notes if n.x>-8 and not (n.hit and n.x<HIT_X-10)]
            duck.update(dt)

            # fail if too many misses or HP depleted
            if miss_count >= MAX_MISSES or (HP_SEGMENTS - miss_count*2) <= 0:
                state="fail"; bg_ch.stop()
            elif not upcoming and not notes:
                state="pass"; bg_ch.stop()
                unlocked = max(unlocked, min(level_idx+2, len(LEVELS)))
                # determine stars for this level based on miss_count
                def stars_for_misses(m):
                    if m == 0: return 3
                    if m in (1,2): return 2
                    if m == 3: return 1
                    return 0
                level_stars = stars_for_misses(miss_count)
                # update best score
                if score > best_score:
                    best_score = score
                    save_best_score(best_score)

        # ===== Draw to pixel canvas =====
        draw_bg(px, laneYs)

        # top-left minimal info (crisp)
        px_text(px, f"Lv{level_idx+1} BPM{lvl['bpm']} L{lvl['lanes']}", 6, 4)
        # score display
        px_text(px, f"SCORE: {score}", 6, 16)
        if last_hit_label:
            px_text(px, f"{last_hit_label}", PX_W-60, 6, color=(255,215,0))

        # buttons
        btn_style_toggle(px, r_style)
        btn_speaker(px, r_music, muted=GAME_CFG.muted)
        if state=="playing":
            btn_eject(px, r_exit)

        # notes & duck
        for n in notes: n.draw(px)
        duck.draw(px)

        # HP 10 segments right side, flash if <=2
        remain = max(0, HP_SEGMENTS - miss_count*2)
        flash_t += dt
        bottom_margin_px = 6
        grid_x, grid_y = PX_W-12, PX_H-58 - bottom_margin_px
        seg_h, gap = 4, 2
        for i in range(HP_SEGMENTS):
            y = grid_y + (HP_SEGMENTS-1-i)*(seg_h+gap)
            px_rect(px, grid_x-1, y-1, 6, seg_h+2, (210,210,210))
            if i < remain:
                if remain <= 2 and int(flash_t*6)%2==0:
                    col = (255,80,80)
                else:
                    col = (46,204,113) if remain>5 else (243,156,18) if remain>2 else (231,76,60)
            else:
                col = (180,180,180)
            px_rect(px, grid_x, y, 4, seg_h, col)

        # overlays
        if state=="menu":
            px_text_center(px, "RHYTHM DUCK // PIXEL", PX_W//2, PX_H//2-28)
            btn_play(px, r_start)
            px_text(px, "W/S or Up/Down  •  Space/Delete  •  M toggle", 12, PX_H-18)
        elif state=="select":
            px_text_center(px, "SELECT LEVEL", PX_W//2, 18)
            mx,my = pygame.mouse.get_pos(); mx//=SCALE; my//=SCALE
            for i,_ in enumerate(LEVELS):
                r = pygame.Rect(30 + i*70, 48, 60, 20)
                hovered = r.collidepoint(mx,my)
                # highlight on hover
                if hovered:
                    btn_box(px, r, active=True)
                else:
                    btn_box(px, r, active=(i<unlocked))
                px_text(px, f"{i+1}", r.x+26, r.y+6)
                if i<unlocked and pygame.mouse.get_pressed()[0] and hovered:
                    level_idx=i; start_level(level_idx); state="playing"
            px_text(px, "Space/Delete to play", PX_W//2-40, PX_H-18)
        elif state=="fail":
            px_text_center(px, "FAILED", PX_W//2, PX_H//2-16)
            px_text_center(px, "Space/Delete/Enter retry", PX_W//2, PX_H//2+2)
            # draw retry button
            btn_box(px, r_retry)
            px_text(px, "RETRY", r_retry.x+8, r_retry.y+1, color=(10,10,10))
        elif state=="pass":
            # non-final levels: show home/next with labels; final level shows trophy
            # show star rating
            try:
                stars = level_stars
            except NameError:
                stars = 0
            sx = PX_W//2 - 18
            sy = PX_H//2 + 28
            for i in range(3):
                col = (255,215,0) if i < stars else (180,180,180)
                px_rect(px, sx + i*12, sy, 8, 8, col)
            if level_idx == len(LEVELS)-1:
                # final clear: larger green message + multi-pixel trophy sprite
                px_text_center(px, "恭喜你通关！", PX_W//2, PX_H//2-30, color=(46,204,113), size=14, outline=True)
                # English fallback visible for systems without CJK fonts
                px_text_center(px, "VICTORY", PX_W//2, PX_H//2-10, color=(46,204,113), size=14, outline=True)
                tx, ty = PX_W//2, PX_H//2+6
                # trophy cup (top)
                px_rect(px, tx-3, ty-6, 6, 4, (255,215,0))
                px_rect(px, tx-2, ty-8, 4, 2, (255,215,0))
                # handles
                px_rect(px, tx-5, ty-4, 2, 2, (200,160,0))
                px_rect(px, tx+3, ty-4, 2, 2, (200,160,0))
                # stem/base
                px_rect(px, tx-1, ty-2, 2, 3, (200,160,0))
                px_rect(px, tx-3, ty+2, 6, 2, (150,120,0))
            else:
                # show congrats text (use Chinese for level 1, English otherwise)
                if level_idx == 0:
                    px_text_center(px, "恭喜你完成！", PX_W//2, PX_H//2-22, color=(46,204,113), outline=True)
                    px_text_center(px, "CLEARED", PX_W//2, PX_H//2-10, color=(46,204,113), size=14, outline=True)
                else:
                    px_text_center(px, "CLEARED", PX_W//2, PX_H//2-22, color=(46,204,113), size=14, outline=True)
                # always draw home/next buttons for non-final levels
                btn_home(px, r_pass_home)
                # English label under home for visibility
                px_text(px, "BACK", r_pass_home.x + 6, r_pass_home.y + r_pass_home.h + 1, color=(10,10,10), size=12, outline=True)
                btn_next(px, r_pass_next, active=(level_idx < len(LEVELS)-1))
                px_text(px, "NEXT", r_pass_next.x + 8, r_pass_next.y + r_pass_next.h + 1, color=(10,10,10), size=12, outline=True)
            # end of pass overlays

        # blit scaled (nearest)
        screen.blit(pygame.transform.scale(px, (SCREEN_W, SCREEN_H)), (0,0))
        pygame.display.flip()

        # save frame if recording
        if record_mode and frames_dir is not None:
            try:
                # save as PNG frames
                count = len([n for n in os.listdir(frames_dir) if n.endswith('.png')])
                fname = os.path.join(frames_dir, f'frame_{count:05d}.png')
                pygame.image.save(screen, fname)
            except Exception as e:
                print('frame save error', e)

        # after level end, if recording was enabled, auto-mux frames into mp4 (requires ffmpeg installed)
        try:
                if record_mode and frames_dir is not None and not frames_muxed and state in ("pass","fail","menu"):
                    # wait until frame files stop growing for a short stable period
                    try:
                        count = len([n for n in os.listdir(frames_dir) if n.endswith('.png')])
                    except Exception:
                        count = 0
                    now = time.time()
                    if count == frames_last_count:
                        if frames_last_stable_since is None:
                            frames_last_stable_since = now
                        elif now - frames_last_stable_since >= 0.6:
                            out_mp4 = os.path.join(out_root, f'rhythm_duck_{ts}.mp4')
                            print('Muxing frames ->', out_mp4)
                            try:
                                import imageio_ffmpeg as _ff
                                ffexe = _ff.get_ffmpeg_exe()
                            except Exception:
                                ffexe = 'ffmpeg'
                            cmd = [ffexe, '-y', '-framerate', '60', '-i', os.path.join(frames_dir, 'frame_%05d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', out_mp4]
                            subprocess.run(cmd)
                            frames_muxed = True
                    else:
                        frames_last_count = count
                        frames_last_stable_since = now
        except Exception as e:
            print('auto-mux error', e)

if __name__ == "__main__":
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=1024)
    main()
