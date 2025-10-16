import sys, math, time
import pygame
import numpy as np

# ================= 像素画布与配色 =================
SCREEN_W, SCREEN_H = 960, 600
PX_W, PX_H = 240, 150
SCALE = SCREEN_W // PX_W
assert SCREEN_W % PX_W == 0 and SCREEN_H % PX_H == 0

# 颜色
C_BG        = (173, 216, 230)   # 天空蓝
C_CITY      = (130, 170, 190)
C_LINE      = (120, 170, 210)   # 浅蓝轨道
C_DUCK      = (252, 202, 62)
C_BEAK      = (255, 120, 60)
C_EYE       = (255, 255, 255)
C_NOTE      = (255, 234, 120)   # 小太阳 / 小云朵主体
C_NOTE_MISS = (150, 160, 170)
C_TEXT      = (30, 40, 60)

# 轨道/判定
HIT_X       = 40                 # 判定线（像素画布坐标）
NOTE_SPD    = 70                 # 像素/秒
NOTE_H      = 5                  # 音符高度（像素）——用于设置轨道粗细
LANE_THICK  = NOTE_H + 2         # 轨道比音符“略粗”
HIT_WIN     = 6                  # 判定窗口（像素）
MOUTH_TIME  = 0.15

# HP/失败规则：10 格，漏 10 颗失败
HP_SEGMENTS = 10
MISSES_TO_FAIL = 10

# 音频
SR    = 44100
VOL   = 0.9
MUTED = False

NOTE_STYLE = "sun"

# ---------- 8-bit 合成 ----------
def square_sound(freq=440, length=0.22, vol=1.0):
    n = int(length * SR)
    t = np.linspace(0, length, n, endpoint=False)
    wave = np.sign(np.sin(2*np.pi*freq*t)).astype(np.float32)
    a = int(0.006*SR); r = int(0.04*SR)
    env = np.ones(n, dtype=np.float32)
    if a>0: env[:a] = np.linspace(0,1,a,endpoint=False)
    if r>0: env[-r:] = np.linspace(1, 0.001, r)
    wave = wave * env * vol
    arr = (wave*32767).astype(np.int16)
    stereo = np.stack([arr, arr], axis=1)
    return pygame.sndarray.make_sound(stereo)

def noise_click(length=0.06, vol=0.45):
    n = int(length * SR)
    w = (np.random.randn(n).astype(np.float32))
    env = np.linspace(1, 0.001, n)
    arr = (w*env*vol*32767).astype(np.int16)
    stereo = np.stack([arr, arr], axis=1)
    return pygame.sndarray.make_sound(stereo)

# 背景旋律（简化“Twinkle Twinkle Little Star”）
A4 = 440.0
def midi_to_hz(m): return 440.0 * (2 ** ((m-69)/12))
def render_song_twinklebpm(bpm=100, bars=8):
    line1 = [60,60,67,67,69,69,67, 65,65,64,64,62,62,60]
    lengths = [1]*6+[2] + [1]*6 + [2]
    beat_sec = 60.0/bpm
    parts = []
    for m,l in zip(line1, lengths):
        dur = l*beat_sec
        n = int(dur*SR)
        t = np.linspace(0,dur,n,endpoint=False)
        wave = np.sign(np.sin(2*np.pi*midi_to_hz(m)*t)).astype(np.float32)
        a = int(0.006*SR); r = int(0.04*SR)
        env = np.ones(n, dtype=np.float32)
        if a>0: env[:a] = np.linspace(0,1,a,endpoint=False)
        if r>0: env[-r:] = np.linspace(1,0.001,r)
        parts.append(wave*env*0.35)
    mono = np.concatenate(parts)
    arr = (mono*32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.stack([arr,arr],axis=1))

# 三轨音高（C4/E4/G4）
LANE_FREQS = [261.63, 329.63, 392.00]

# 关卡（避免同拍多轨）
LEVELS = [
    dict(name="Lv1", bpm=92,  lanes=2, pattern=[
        (0,0),(1,0),(2,1),(3,1),
        (4,0),(5,1),(6,0),(7,1),
    ]),
    dict(name="Lv2", bpm=108, lanes=3, pattern=[
        (0,0),(1,1),(2,2),(3,1),
        (4,0),(5,1),(6,2),(7,1),
        (8,0),(9,1),(10,2),(11,1),
    ]),
    dict(name="Lv3", bpm=122, lanes=3, pattern=[
        (0,0),(0.75,1),(1.5,2),(2.25,1),
        (3.0,0),(3.75,1),(4.5,2),(5.25,1),
        (6.0,2),(6.75,1),(7.5,0),(8.25,1),
    ]),
]

# =============== 像素绘制工具 ===============
def px_rect(s, x,y,w,h,c): s.fill(c, pygame.Rect(x,y,w,h))
def px_text(s, txt, x,y, color=C_TEXT):
    font = pygame.font.SysFont("Courier", 10, bold=True)
    s.blit(font.render(txt, True, color), (x,y))

def draw_bg(s, laneYs):
    s.fill(C_BG)
    px_rect(s, 0, PX_H-20, PX_W, 20, C_CITY)
    for y in laneYs:
        px_rect(s, 0, y - LANE_THICK//2, PX_W, LANE_THICK, C_LINE)
    px_rect(s, HIT_X, laneYs[0]-8, 1, (laneYs[-1]-laneYs[0])+16, (60,110,155))

# 小鸭像素画
def draw_pixel_duck(surf, x, y, mouth=False):
    px_rect(surf, x-6, y-4, 10, 8, C_DUCK)
    px_rect(surf, x+4, y-2, 4, 4, C_DUCK)
    px_rect(surf, x+6, y-3, 2, 2, C_EYE)
    px_rect(surf, x-4, y+4, 4, 3, C_DUCK)
    w = 4 if mouth else 2
    px_rect(surf, x+8, y-1, w, 2, C_BEAK)

# 音符：小太阳 or 小云朵
NOTE_STYLE = "sun"

def draw_sun(s, cx, cy, miss=False):
    col = C_NOTE_MISS if miss else C_NOTE
    px_rect(s, cx-1, cy-1, 3, 3, col)
    px_rect(s, cx-2, cy, 5, 1, col)
    px_rect(s, cx, cy-2, 1, 5, col)

def draw_cloud(s, cx, cy, miss=False):
    col = C_NOTE_MISS if miss else C_NOTE
    px_rect(s, cx-3, cy-1, 3, 2, col)
    px_rect(s, cx-1, cy-2, 3, 3, col)
    px_rect(s, cx+2, cy-1, 3, 2, col)

def draw_note(s, x,y, miss=False):
    if NOTE_STYLE == "cloud": draw_cloud(s, int(x), int(y), miss)
    else: draw_sun(s, int(x), int(y), miss)

# =============== Pixel 特效 (小像素效果) ===============
class PxHit:
    def __init__(self, x, y):
        self.x = int(x); self.y = int(y)
        self.t = 0.0; self.dur = 0.28
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, s):
        if not self.alive(): return
        frac = self.t / self.dur
        size = 1 + int(4 * frac)
        r = 255; g = 230 - int(140*frac); b = 100
        for dx in range(-size, size+1):
            for dy in range(-size, size+1):
                if abs(dx) + abs(dy) <= size:
                    px_rect(s, self.x+dx, self.y+dy, 1, 1, (r, max(0,g), b))

class PxText:
    def __init__(self, x, y, txt, color=(255,255,255)):
        self.x = int(x); self.y = int(y); self.txt = txt; self.color = color
        self.t = 0.0; self.dur = 0.8
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, s):
        if not self.alive(): return
        frac = self.t / self.dur
        yoff = int(-18 * frac)
        px_text(s, self.txt, self.x-6, self.y + yoff, self.color)

class PxMissFlash:
    def __init__(self):
        self.t = 0.0; self.dur = 0.28
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, s):
        if not self.alive(): return
        frac = self.t / self.dur
        alpha = int(160 * (1 - frac))
        surf = pygame.Surface((PX_W, PX_H), pygame.SRCALPHA)
        surf.fill((220,40,40,alpha))
        s.blit(surf, (0,0))

# =============== 游戏对象 ===============
class Note:
    def __init__(self, x, lane, y):
        self.x=x; self.lane=lane; self.y=y
        self.hit=False; self.missed=False
    def update(self, dt):
        self.x -= NOTE_SPD*dt
        if not self.hit and not self.missed and self.x < HIT_X - HIT_WIN:
            self.missed = True
    def draw(self, s): draw_note(s, self.x, self.y, self.missed)

class Duck:
    def __init__(self, laneYs):
        self.lanes=laneYs; self.idx=min(1,len(laneYs)-1)
        self.y=self.lanes[self.idx]; self.mouth=0.0
    def set_lanes(self, laneYs):
        self.lanes=laneYs; self.idx=min(self.idx, len(laneYs)-1); self.y=self.lanes[self.idx]
    def up(self):   self.idx=max(0,self.idx-1); self.y=self.lanes[self.idx]
    def down(self): self.idx=min(len(self.lanes)-1, self.idx+1); self.y=self.lanes[self.idx]
    def eat(self):  self.mouth = MOUTH_TIME
    def update(self, dt): 
        if self.mouth>0: self.mouth -= dt
    def draw(self, s): draw_pixel_duck(s, HIT_X-4, int(self.y), mouth=(self.mouth>0))

# =============== 调度 & 背景旋律 ===============
def lane_ys_for(nlanes): return [60, 90] if nlanes==2 else [50, 80, 110]

def build_schedule(level):
    bpm = level["bpm"]; beat = 60.0/bpm
    start_x = PX_W + 12
    travel = (start_x - HIT_X)/NOTE_SPD
    seq=[]
    used_beats=set()   # 防止同拍多轨
    for beatpos, lane in level["pattern"]:
        if beatpos in used_beats: continue
        used_beats.add(beatpos)
        spawn = max(0.0, beatpos*beat - travel)
        seq.append(dict(spawn=spawn, lane=lane))
    return sorted(seq, key=lambda d:d["spawn"])

# =============== 主程序 ===============
def main():
    global MUTED, NOTE_STYLE
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=1024)
    pygame.init()
    pygame.font.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Rhythm Duck – Pixel (v3)")
    clock = pygame.time.Clock()

    px = pygame.Surface((PX_W, PX_H)).convert()

    # 轨道三音 + 吃到音效
    lane_sounds = [square_sound(f, 0.24, VOL) for f in LANE_FREQS]
    sfx_eat     = noise_click(0.05, 0.45)

    # 背景旋律声道
    bg_channel = pygame.mixer.Channel(0)
    def play_background(bpm):
        snd = render_song_twinklebpm(bpm=bpm)
        if not MUTED: bg_channel.play(snd, loops=-1)  # 循环播放
        else: bg_channel.stop()

    # 状态
    state="menu"     # menu/select/playing/fail/pass
    unlocked=1
    level_idx=0
    lvl = LEVELS[level_idx]
    laneYs = lane_ys_for(lvl["lanes"])
    duck = Duck(laneYs)

    misses = 0  # 漏吃数
    t_elapsed=0.0
    upcoming=[]; notes=[]
    effects = []
    hp_flash_timer=0.0

    def hp_color():
        nonlocal hp_flash_timer
        remain = HP_SEGMENTS - misses
        base = (46, 204, 113) if remain>5 else (243,156,18) if remain>2 else (231,76,60)
        if remain<=2:
            hp_flash_timer += dt
            if int(hp_flash_timer*4) % 2 == 0:  # 闪烁
                return (255,80,80)
        return base

    def start_level(i):
        nonlocal lvl,laneYs,t_elapsed,upcoming,notes,misses,effects
        lvl = LEVELS[i]; laneYs = lane_ys_for(lvl["lanes"])
        duck.set_lanes(laneYs)
        t_elapsed=0.0; upcoming=build_schedule(lvl); notes=[]; misses=0; effects=[]
        play_background(lvl["bpm"])

    # 像素按钮（只显示符号，避免溢出）
    btn_mute = pygame.Rect(PX_W-18, 4, 14, 12)      # ♪ / 🔇
    btn_exit = pygame.Rect(PX_W-18, PX_H-16, 14, 12) # ⏏
    btn_start= pygame.Rect(PX_W//2-7, PX_H//2+6, 14, 12) # ▶
    btn_style= pygame.Rect(PX_W-36, 4, 14, 12)      # ☁/☀ 切换音符样式

    def draw_btn(s, r, glyph, active=True):
        col = (230,230,230) if active else (180,180,180)
        px_rect(s, r.x, r.y, r.w, r.h, col)
        px_text(s, glyph, r.x+2, r.y+1, (20,20,20) if active else (80,80,80))

    while True:
        dt = clock.tick(60)/1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q): pygame.quit(); sys.exit(0)
                if e.key == pygame.K_m:
                    MUTED = not MUTED
                    if MUTED: bg_channel.stop()
                    else: play_background(lvl["bpm"])

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
                if btn_mute.collidepoint(mx,my):
                    MUTED = not MUTED
                    if MUTED: bg_channel.stop()
                    else: play_background(lvl["bpm"])
                elif btn_style.collidepoint(mx,my):
                    NOTE_STYLE = "cloud" if NOTE_STYLE=="sun" else "sun"
                elif state=="menu" and btn_start.collidepoint(mx,my):
                    state="select"
                elif state=="playing" and btn_exit.collidepoint(mx,my):
                    state="select"; bg_channel.stop()

        # ========== Update ==========
        if state=="playing":
            t_elapsed += dt
            while upcoming and upcoming[0]["spawn"] <= t_elapsed:
                info = upcoming.pop(0)
                notes.append(Note(PX_W+10, info["lane"], laneYs[info["lane"]]))

            for n in notes: n.update(dt)

            for n in notes:
                if not n.hit and not n.missed and n.lane==duck.idx and abs(n.x-HIT_X)<=HIT_WIN:
                    n.hit=True; duck.eat()
                    if not MUTED:
                        lane_sounds[min(n.lane,2)].play()
                        sfx_eat.play()
                    # spawn effects
                    effects.append(PxHit(n.x, n.y))
                    effects.append(PxText(n.x, n.y, "HIT!", color=(255,240,200)))

            # 统计漏吃
            for n in notes:
                if n.missed:
                    misses += 1
                    n.missed = False
                    effects.append(PxMissFlash())

            # 移除离场
            notes = [n for n in notes if n.x>-8 and not (n.hit and n.x<HIT_X-10)]
            duck.update(dt)

            # 胜负
            if misses >= MISSES_TO_FAIL:
                state="fail"; bg_channel.stop()
            elif not upcoming and not notes:
                state="pass"
                bg_channel.stop()
                unlocked = max(1, min(level_idx+2, len(LEVELS)))

        # ========== Draw 到像素画布 ==========
        draw_bg(px, laneYs)
        px_text(px, f"{lvl['name']} BPM{lvl['bpm']} L{lvl['lanes']}", 6, 4)

        draw_btn(px, btn_style, "☀" if NOTE_STYLE=="sun" else "☁")
        draw_btn(px, btn_mute,  "♪" if not MUTED else "🔇")
        if state=="playing": draw_btn(px, btn_exit, "⏏")

        # 音符 & 鸭
        for n in notes: n.draw(px)
        duck.draw(px)

        # effects: draw then update
        for ef in effects: ef.draw(px)
        for ef in effects: ef.update(dt)
        effects = [ef for ef in effects if ef.alive()]

        # HP 10 格（右侧小格子），≤2 闪红
        remain = max(0, HP_SEGMENTS - misses)
        grid_x, grid_y = PX_W-10, PX_H-58
        seg_h, seg_gap = 4, 2
        for i in range(HP_SEGMENTS):
            y = grid_y + (HP_SEGMENTS-1-i)*(seg_h+seg_gap)
            col = hp_color() if i < remain else (180,180,180)
            px_rect(px, grid_x-1, y-1, 6, seg_h+2, (210,210,210))
            px_rect(px, grid_x,   y,   4, seg_h,   col)

        # 状态覆盖文本
        if state=="menu":
            px_text(px, "RHYTHM DUCK // PIXEL", PX_W//2-70, PX_H//2-28)
            draw_btn(px, btn_start, "▶")
            px_text(px, "W/S or Up/Down  •  Space/Delete  •  M toggle", 12, PX_H-18)
        elif state=="select":
            px_text(px, "SELECT LEVEL", PX_W//2-36, 18)
            for i,L in enumerate(LEVELS):
                r = pygame.Rect(30 + i*70, 48, 60, 20)
                act = (i < unlocked)
                draw_btn(px, r, f"{i+1}")
                if act and pygame.mouse.get_pressed()[0]:
                    mx,my = pygame.mouse.get_pos(); mx//=SCALE; my//=SCALE
                    if r.collidepoint(mx,my):
                        level_idx=i; start_level(level_idx); state="playing"
            px_text(px, "Space/Delete to play", PX_W//2-40, PX_H-18)
        elif state=="fail":
            px_text(px, "FAILED", PX_W//2-18, PX_H//2-16)
            px_text(px, "Space/Delete retry", PX_W//2-40, PX_H//2+2)
        elif state=="pass":
            px_text(px, "CLEARED", PX_W//2-22, PX_H//2-16)
            px_text(px, "Space/Delete level select", PX_W//2-54, PX_H//2+2)

        screen.blit(pygame.transform.scale(px, (SCREEN_W, SCREEN_H)), (0,0))
        pygame.display.flip()

if __name__ == "__main__":
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=1024)
    main()
