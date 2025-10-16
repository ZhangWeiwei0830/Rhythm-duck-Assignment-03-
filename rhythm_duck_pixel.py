import sys, math, time
import pygame
import numpy as np

# ========= 全局/像素画布 =========
SCREEN_W, SCREEN_H = 960, 600           # 外层屏幕（保持不变）
PX_W, PX_H = 240, 150                   # 内层“像素画布”分辨率（低像素）
SCALE = SCREEN_W // PX_W                # 放大倍数（取整，NEAREST）
assert SCREEN_W % PX_W == 0 and SCREEN_H % PX_H == 0, "请让屏幕尺寸是像素画布的整数倍"

# 颜色（尽量 GameBoy-like）
C_BG = (173, 216, 230)      # 天空蓝
C_CITY = (130, 170, 190)
C_LINE = (70, 100, 130)
C_DUCK = (252, 202, 62)
C_BEAK = (255, 120, 60)
C_EYE = (255, 255, 255)
C_NOTE = (255, 230, 90)
C_NOTE_MISS = (140, 140, 140)
C_TEXT = (30, 40, 60)

# 轨道/判定
HIT_X = 40                   # 在像素画布坐标下的判定 X
NOTE_SPD = 70                # 像素/秒（像素画布尺度）
HIT_WIN = 6                  # 命中窗口（像素）
MAX_HP = 100
HP_MISS = 12
MOUTH_TIME = 0.15

# 音频（保证更响 & 更易听见）
SR = 44100
VOL = 0.9
MUTED = False

def square_sound(freq=440, length=0.25, vol=1.0):
    """更响的方波 + 平滑包络，返回 pygame.Sound"""
    n = int(length * SR)
    t = np.linspace(0, length, n, endpoint=False)
    wave = np.sign(np.sin(2*np.pi*freq*t)).astype(np.float32)  # 方波
    # 简单 ADSR，避免爆音
    a = int(0.005*SR); r = int(0.04*SR)
    env = np.ones(n, dtype=np.float32)
    if a>0: env[:a] = np.linspace(0, 1, a, endpoint=False)
    if r>0: env[-r:] = np.linspace(1, 0.001, r)
    wave = wave * env * vol
    arr = (wave * 32767).astype(np.int16)
    stereo = np.stack([arr, arr], axis=1)
    return pygame.sndarray.make_sound(stereo)

def noise_click(length=0.08, vol=0.4):
    n = int(length * SR)
    w = (np.random.randn(n).astype(np.float32))
    a = int(0.004*SR)
    env = np.ones(n, dtype=np.float32)
    env[:a] = np.linspace(0, 1, a, endpoint=False)
    env = env * np.linspace(1, 0.001, n)
    w = w * env * vol
    arr = (w * 32767).astype(np.int16)
    stereo = np.stack([arr, arr], axis=1)
    return pygame.sndarray.make_sound(stereo)

# 三条轨的 8-bit 音高（C4/E4/G4）
LANE_FREQS = [261.63, 329.63, 392.00]

# 关卡（像素坐标节拍）
LEVELS = [
    dict(name="Lv1 Warmup", bpm=92, lanes=2, pattern=[
        (0,0),(1,0),(2,1),(3,1), (4,0),(5,1),(6,0),(7,1),
    ]),
    dict(name="Lv2 Steps", bpm=108, lanes=3, pattern=[
        (0,0),(1,1),(2,2),(3,1), (4,0),(5,1),(6,2),(7,1),
        (8,0),(9,1),(10,2),(11,1),
    ]),
    dict(name="Lv3 Dash", bpm=122, lanes=3, pattern=[
        (0,0),(0.5,1),(1,2),(1.5,1),
        (2,0),(2.5,1),(3,2),(3.5,1),
        (4,2),(4.5,1),(5,0),(5.5,1),
        (6,2),(6.5,1),(7,0),(7.5,1),
    ]),
]

def lane_ys(lanes):
    # 像素画布内的轨道 Y
    return [60, 90] if lanes==2 else [50, 80, 110]

# ---------- 像素绘制工具 ----------
def px_rect(surface, x, y, w, h, color):
    surface.fill(color, pygame.Rect(x, y, w, h))

def px_text(surface, s, x, y, color=C_TEXT):
    # 用系统字体渲染到小画布，然后再缩放；为了 crisp，字号选小一点
    font = pygame.font.SysFont("Courier", 10, bold=True)
    img = font.render(s, True, color)
    surface.blit(img, (x, y))

def draw_pixel_duck(surf, x, y, mouth_open=False):
    # 8x8 像素级“鸭”，然后整体放大（这里直接画在低分辨率画布上）
    # 身体块
    px_rect(surf, x-6, y-4, 10, 8, C_DUCK)
    px_rect(surf, x+4, y-2, 4, 4, C_DUCK)     # 头
    px_rect(surf, x-4, y+4, 4, 3, C_DUCK)     # 尾
    # 眼睛
    px_rect(surf, x+6, y-3, 2, 2, C_EYE)
    # 嘴：闭嘴2px，张嘴4px
    w = 4 if mouth_open else 2
    px_rect(surf, x+8, y-1, w, 2, C_BEAK)

def draw_pixel_star(surf, cx, cy, miss=False):
    col = C_NOTE_MISS if miss else C_NOTE
    # 3x3/十字星
    px_rect(surf, cx-1, cy-1, 3, 1, col)
    px_rect(surf, cx-1, cy+1, 3, 1, col)
    px_rect(surf, cx-1, cy,   1, 1, col)
    px_rect(surf, cx+1, cy,   1, 1, col)

def draw_bg(surf, lanesY):
    surf.fill(C_BG)
    # 地平线
    px_rect(surf, 0, PX_H-20, PX_W, 20, C_CITY)
    # 轨道线（像素风）
    for y in lanesY:
        px_rect(surf, 0, y, PX_W, 1, C_LINE)
    # 判定竖线
    px_rect(surf, HIT_X, lanesY[0]-6, 1, (lanesY[-1]-lanesY[0])+12, (50,90,130))

# ---------- 对象 ----------
class Note:
    def __init__(self, x, lane, y):
        self.x = x; self.lane = lane; self.y = y
        self.hit = False; self.missed = False
    def update(self, dt):
        self.x -= NOTE_SPD * dt
        if not self.hit and not self.missed and self.x < HIT_X - HIT_WIN:
            self.missed = True
    def draw(self, surf):
        draw_pixel_star(surf, int(self.x), int(self.y), miss=self.missed)

class Duck:
    def __init__(self, lanesY):
        self.lanesY = lanesY
        self.idx = min(1, len(lanesY)-1)
        self.y = lanesY[self.idx]
        self.mouth = 0.0
    def set_lanes(self, lanesY):
        self.lanesY = lanesY
        self.idx = min(self.idx, len(lanesY)-1)
        self.y = self.lanesY[self.idx]
    def up(self):
        if self.idx>0: self.idx-=1; self.y=self.lanesY[self.idx]
    def down(self):
        if self.idx<len(self.lanesY)-1: self.idx+=1; self.y=self.lanesY[self.idx]
    def eat(self): self.mouth = MOUTH_TIME
    def update(self, dt):
        if self.mouth>0: self.mouth -= dt
    def draw(self, surf):
        draw_pixel_duck(surf, HIT_X-4, int(self.y), mouth_open=(self.mouth>0))

# ---------- 谱面调度 ----------
def schedule_for(level):
    bpm = level["bpm"]; beat_sec = 60.0/bpm
    start_x = PX_W + 12
    travel = (start_x - HIT_X) / NOTE_SPD
    seq=[]
    for beat,lane in level["pattern"]:
        t=beat*beat_sec
        seq.append(dict(spawn=max(0.0, t-travel), lane=lane))
    return seq


# ---------- Pixel 特效 (小尺寸像素风) ----------
class PxHit:
    def __init__(self, x, y):
        self.x = int(x); self.y = int(y)
        self.t = 0.0; self.dur = 0.28
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, surf):
        if not self.alive(): return
        frac = self.t / self.dur
        size = 1 + int(5 * frac)
        # warm yellow -> fade
        r = 255; g = 230 - int(120*frac); b = 90
        for dx in range(-size, size+1):
            for dy in range(-size, size+1):
                if abs(dx) + abs(dy) <= size:
                    px_rect(surf, self.x+dx, self.y+dy, 1, 1, (r, max(0,g), b))

class PxText:
    def __init__(self, x, y, txt, color=(255,255,255)):
        self.x = int(x); self.y = int(y); self.txt = txt; self.color = color
        self.t = 0.0; self.dur = 0.8
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, surf):
        if not self.alive(): return
        frac = self.t / self.dur
        yoff = int(-18 * frac)
        px_text(surf, self.txt, self.x-6, self.y + yoff, self.color)

class PxMissFlash:
    def __init__(self):
        self.t = 0.0; self.dur = 0.28
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, surf):
        if not self.alive(): return
        frac = self.t / self.dur
        alpha = int(160 * (1 - frac))
        s = pygame.Surface((PX_W, PX_H), pygame.SRCALPHA)
        s.fill((220, 40, 40, alpha))
        surf.blit(s, (0,0))

# ---------- 主函数 ----------
def main():
    global MUTED
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=1024)  # 更大的 buffer 在 mac 上更稳
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Rhythm Duck – Pixel Edition")
    clock = pygame.time.Clock()

    # 小画布（像素风）
    px_surface = pygame.Surface((PX_W, PX_H)).convert()
    # 预生成声音（方波更清晰）
    lane_sounds = [square_sound(f, 0.28, VOL) for f in LANE_FREQS]
    sfx_eat = noise_click(0.06, 0.35)

    # 状态
    state = "menu"  # menu/select/playing/fail/pass
    unlocked = 1
    level_idx = 0
    lvl = LEVELS[level_idx]
    lanesY = lane_ys(lvl["lanes"])
    duck = Duck(lanesY)

    # 关卡运行
    hp = MAX_HP
    t_elapsed = 0.0
    upcoming = []
    notes = []
    effects = []

    def start_level(i):
        nonlocal lvl, lanesY, hp, t_elapsed, upcoming, notes
        lvl = LEVELS[i]
        lanesY = lane_ys(lvl["lanes"])
        duck.set_lanes(lanesY)
        hp = MAX_HP
        t_elapsed = 0.0
        notes = []
        upcoming = sorted(schedule_for(lvl), key=lambda d:d["spawn"])

    # UI 区域（像素坐标）
    mute_rect_px = pygame.Rect(PX_W-40, 6, 34, 12)
    exit_rect_px = pygame.Rect(PX_W-40, PX_H-16, 34, 10)
    start_rect_px = pygame.Rect(PX_W//2-20, PX_H//2+6, 40, 14)

    def draw_button_px(s, r, label, active=True):
        col = (230,230,230) if active else (180,180,180)
        px_rect(s, r.x, r.y, r.w, r.h, col)
        px_text(s, label, r.x+4, r.y+2, (20,20,20) if active else (80,80,80))

    while True:
        dt = clock.tick(60)/1000.0

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q):
                    pygame.quit(); sys.exit(0)
                if e.key == pygame.K_m:
                    MUTED = not MUTED

                if state in ("menu","select","fail","pass"):
                    if e.key in (pygame.K_SPACE, pygame.K_DELETE):
                        if state == "menu":
                            state = "select"
                        elif state == "select":
                            start_level(level_idx); state = "playing"
                        elif state == "fail":
                            start_level(level_idx); state = "playing"
                        elif state == "pass":
                            state = "select"

                if state == "playing":
                    if e.key in (pygame.K_w, pygame.K_UP): duck.up()
                    if e.key in (pygame.K_s, pygame.K_DOWN): duck.down()

            if e.type == pygame.MOUSEBUTTONDOWN:
                # 转成像素画布坐标
                mx, my = pygame.mouse.get_pos()
                mx //= SCALE; my //= SCALE
                if mute_rect_px.collidepoint(mx, my):
                    MUTED = not MUTED
                elif state == "menu" and start_rect_px.collidepoint(mx, my):
                    state = "select"
                elif state == "playing" and exit_rect_px.collidepoint(mx, my):
                    state = "select"

        # ----- Update -----
        if state == "playing":
            t_elapsed += dt
            while upcoming and upcoming[0]["spawn"] <= t_elapsed:
                info = upcoming.pop(0)
                y = lanesY[info["lane"]]
                notes.append(Note(PX_W + 10, info["lane"], y))

            for n in notes: n.update(dt)

            # 命中
            for n in notes:
                if not n.hit and not n.missed and n.lane == duck.idx:
                    if abs(n.x - HIT_X) <= HIT_WIN:
                        n.hit = True
                        duck.eat()
                        if not MUTED:
                            lane_sounds[min(n.lane, 2)].play()
                            sfx_eat.play()
                        # spawn pixel hit + text
                        effects.append(PxHit(n.x, n.y))
                        effects.append(PxText(n.x, n.y, "HIT!", color=(255,240,200)))

            # Miss 扣血（只扣一次）
            for n in notes:
                if n.missed:
                    hp -= HP_MISS
                    n.missed = False
                    effects.append(PxMissFlash())

            notes = [n for n in notes if n.x > -8 and not (n.hit and n.x < HIT_X-10)]
            duck.update(dt)

            if hp <= 0: state = "fail"
            elif not upcoming and not notes:
                state = "pass"
                unlocked = max(unlocked, min(level_idx+2, len(LEVELS)))

        # ----- Draw 到像素画布 -----
        draw_bg(px_surface, lanesY)
        # 顶栏文案
        px_text(px_surface, f"{lvl['name']} BPM{lvl['bpm']} L{lvl['lanes']}", 6, 4)
        # 按钮
        draw_button_px(px_surface, mute_rect_px, "MUSIC" if not MUTED else "MUTE", active=not MUTED)
        if state == "playing":
            draw_button_px(px_surface, exit_rect_px, "EXIT", active=True)

        # 音符 & 鸭
        for n in notes: n.draw(px_surface)
        duck.draw(px_surface)

        # 特效：在鸭与音符之后绘制
        for ef in effects:
            ef.draw(px_surface)

        # update effects and cull
        for ef in effects:
            ef.update(dt)
        effects = [ef for ef in effects if ef.alive()]

        # HP 条（像素风）
        # 右侧竖条
        bar_h = 40; bar_w=4; bx=PX_W-10; by=PX_H-bar_h-6
        px_rect(px_surface, bx-1, by-1, bar_w+2, bar_h+2, (200,200,200))
        h = int(bar_h * (hp if state=="playing" else MAX_HP)/MAX_HP)
        col = (46, 204, 113) if hp>50 else (243, 156, 18) if hp>25 else (231, 76, 60)
        px_rect(px_surface, bx, by+(bar_h-h), bar_w, h, col)

        # 状态覆盖
        if state == "menu":
            px_text(px_surface, "RHYTHM DUCK // PIXEL", PX_W//2-70, PX_H//2-30)
            draw_button_px(px_surface, start_rect_px, "START", True)
            px_text(px_surface, "W/S or Up/Down  //  Space/Delete start  //  M mute", 18, PX_H-18)
        elif state == "select":
            px_text(px_surface, "SELECT LEVEL:", PX_W//2-40, 20)
            # 三个关卡按钮（像素）
            btns=[]
            for i,L in enumerate(LEVELS):
                rx = 30 + i*70; ry = 50
                r = pygame.Rect(rx, ry, 60, 20)
                act = (i < unlocked)
                draw_button_px(px_surface, r, f"{i+1}. {L['name']}", act)
                # 点击选择
                if act and pygame.mouse.get_pressed()[0]:
                    mx,my = pygame.mouse.get_pos(); mx//=SCALE; my//=SCALE
                    if r.collidepoint(mx,my):
                        level_idx = i
                        start_level(level_idx); state="playing"
            px_text(px_surface, "Space/Delete to play", PX_W//2-40, PX_H-18)
        elif state == "fail":
            px_text(px_surface, "STAGE FAILED", PX_W//2-40, PX_H//2-20)
            px_text(px_surface, "Space/Delete to retry", PX_W//2-46, PX_H//2-4)
        elif state == "pass":
            msg = "ALL CLEARED!" if unlocked==len(LEVELS) else "STAGE CLEARED"
            px_text(px_surface, msg, PX_W//2-40, PX_H//2-20)
            px_text(px_surface, "Space/Delete for level select", PX_W//2-64, PX_H//2-4)

        # 放大到屏幕（NEAREST 保持像素）
        surf = pygame.transform.scale(px_surface, (SCREEN_W, SCREEN_H))
        screen.blit(surf, (0,0))
        pygame.display.flip()

if __name__ == "__main__":
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=1024)
    pygame.init()
    pygame.font.init()
    main()
