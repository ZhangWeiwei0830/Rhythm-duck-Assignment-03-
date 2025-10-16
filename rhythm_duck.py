import sys, math, numpy as np, pygame

# ---------------- 基本配置 ----------------
SCREEN_W, SCREEN_H = 960, 600
BG_COLOR = (230, 245, 255)
CITY_COLOR = (190, 215, 225)
LINE_COLOR = (180, 180, 180)
HIT_LINE_X = 180                 # 判定线 X
NOTE_SPEED = 340                 # 音符速度（像素/秒）
HIT_WINDOW = 36                  # 判定窗口（像素）
DUCK_MOUTH_TIME = 0.15           # 张嘴持续
MAX_HP = 100
HP_MISS = 12

# 声音
SR = 44100
VOL_MASTER = 0.65
MUTED = False

def sine_sound(freq=440, length=0.18, vol=0.9):
    n = int(length * SR)
    t = np.linspace(0, length, n, endpoint=False)
    env = np.linspace(0, 1, int(0.01*SR), endpoint=False)
    env = np.pad(env, (0, n-len(env)), 'linear_ramp', end_values=(1, 0.001))
    wave = np.sin(2*np.pi*freq*t) * env * vol
    arr = (wave * 32767).astype(np.int16)
    stereo = np.stack([arr, arr], axis=1)
    return pygame.sndarray.make_sound(stereo)

# 三个轨道的音高（C4/E4/G4）
LANE_FREQS = [261.63, 329.63, 392.00]
LANE_SOUNDS = []

# ---------------- 关卡定义 ----------------
# 每个关卡：name、bpm、lanes（2或3）、pattern=[(beat, laneIdx)]
LEVELS = [
    dict(name="Level 1 – Warmup", bpm=92, lanes=2, pattern=[
        (0,0),(1,0),(2,1),(3,1),
        (4,0),(5,0),(6,1),(7,1),
        (8,0),(9,1),(10,0),(11,1),
    ]),
    dict(name="Level 2 – Steps", bpm=108, lanes=3, pattern=[
        (0,0),(1,1),(2,2),(3,1),
        (4,0),(5,1),(6,2),(7,1),
        (8,0),(9,1),(10,2),(11,1),
        (12,0),(13,1),(14,2),(15,1),
    ]),
    dict(name="Level 3 – Sprint", bpm=122, lanes=3, pattern=[
        (0,0),(0.5,1),(1,2),(1.5,1),
        (2,0),(2.5,1),(3,2),(3.5,1),
        (4,2),(4.5,1),(5,0),(5.5,1),
        (6,2),(6.5,1),(7,0),(7.5,1),
    ])
]

# ---------------- 工具与绘制 ----------------
def lane_ys_for(lanes):
    if lanes == 2:
        return [260, 360]
    return [220, 320, 420]

def draw_bg(surf, lane_ys):
    surf.fill(BG_COLOR)
    pygame.draw.rect(surf, CITY_COLOR, (0, SCREEN_H-160, SCREEN_W, 160))
    for y in lane_ys:
        pygame.draw.line(surf, LINE_COLOR, (0, y), (SCREEN_W, y), 2)
    pygame.draw.line(surf, (90,130,170), (HIT_LINE_X, lane_ys[0]-50),
                     (HIT_LINE_X, lane_ys[-1]+50), 4)

def text(surf, s, pos, size=28, color=(40,40,40), center=False):
    font = pygame.font.SysFont(None, size)
    img = font.render(s, True, color)
    rect = img.get_rect()
    rect.center = pos if center else rect.move(pos).topleft
    surf.blit(img, rect if center else img.get_rect(topleft=pos))

def draw_button(surf, rect, label, active=True):
    pygame.draw.rect(surf, (230,230,230), rect, border_radius=8)
    pygame.draw.rect(surf, (60,60,60), rect, 2, border_radius=8)
    font = pygame.font.SysFont(None, 24)
    col = (30,30,30) if active else (130,130,130)
    surf.blit(font.render(label, True, col), (rect.x+12, rect.y+7))

def draw_hp(surf, hp):
    w,h = 18, 170
    x,y = SCREEN_W-40, SCREEN_H-h-40
    pygame.draw.rect(surf, (210,210,210), (x,y,w,h), border_radius=6)
    hh = int(h * max(hp,0) / MAX_HP)
    col = (60,220,80) if hp>50 else (255,180,0) if hp>25 else (240,80,60)
    pygame.draw.rect(surf, col, (x, y+(h-hh), w, hh), border_radius=6)

# ---------------- 游戏对象 ----------------
class Note:
    def __init__(self, x, lane_idx, y, speed, freq_idx):
        self.x = x; self.lane_idx = lane_idx; self.y = y
        self.speed = speed; self.hit = False; self.missed = False
        self.freq_idx = freq_idx
    def update(self, dt):
        self.x -= self.speed * dt
        if not self.hit and not self.missed and self.x < HIT_LINE_X - HIT_WINDOW:
            self.missed = True
    def draw(self, surf):
        size = 18
        pts=[]
        for i in range(10):
            ang = i*math.pi/5
            r = size if i%2==0 else size/2
            pts.append((self.x + r*math.cos(ang), self.y + r*math.sin(ang)))
        color = (255,215,0) if not self.missed else (200,200,200)
        pygame.draw.polygon(surf, color, pts)

class Duck:
    def __init__(self, lane_ys):
        self.lanes = lane_ys
        self.idx = min(1, len(lane_ys)-1)
        self.y = self.lanes[self.idx]
        self.mouth = 0.0
    def set_lanes(self, lane_ys):
        self.lanes = lane_ys
        self.idx = min(self.idx, len(lane_ys)-1)
        self.y = self.lanes[self.idx]
    def up(self):
        if self.idx>0: self.idx -= 1; self.y = self.lanes[self.idx]
    def down(self):
        if self.idx<len(self.lanes)-1: self.idx += 1; self.y = self.lanes[self.idx]
    def eat(self):
        self.mouth = DUCK_MOUTH_TIME
    def update(self, dt):
        if self.mouth>0: self.mouth -= dt
    def draw(self, surf):
        x,y = HIT_LINE_X, self.y
        body=(255,196,0); eye=(255,255,255); beak=(255,120,60)
        pygame.draw.circle(surf, body, (x,y), 26)
        pygame.draw.circle(surf, eye, (x+10,y-7), 5)
        mouth = 20 if self.mouth>0 else 10
        pts=[(x+20,y),(x+20+mouth,y-6),(x+20+mouth,y+6)]
        pygame.draw.polygon(surf, beak, pts)

# ---------------- 简单特效 ----------------
class HitEffect:
    def __init__(self, x, y):
        self.x = x; self.y = y
        self.t = 0.0; self.dur = 0.28
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, surf):
        if not self.alive(): return
        frac = self.t / self.dur
        r = int(8 + 48 * frac)
        alpha = int(220 * (1 - frac))
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (255, 255, 255, alpha), (r, r), r)
        pygame.draw.circle(s, (255, 220, 80, max(0, alpha-80)), (r, r), int(r*0.6))
        surf.blit(s, (int(self.x-r), int(self.y-r)))

class TextPop:
    def __init__(self, x, y, text, color=(255,255,255)):
        self.x = x; self.y = y; self.t = 0.0; self.dur = 0.8; self.text = text; self.color = color
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, surf):
        if not self.alive(): return
        frac = self.t / self.dur
        alpha = int(255 * (1 - frac))
        yoff = int(-30 * frac)
        f = pygame.font.SysFont(None, 26)
        img = f.render(self.text, True, self.color)
        img.set_alpha(alpha)
        rect = img.get_rect(center=(int(self.x), int(self.y + yoff)))
        surf.blit(img, rect)

class MissFlash:
    def __init__(self):
        self.t = 0.0; self.dur = 0.35
    def update(self, dt):
        self.t += dt
    def alive(self):
        return self.t < self.dur
    def draw(self, surf):
        frac = max(0.0, min(1.0, self.t / self.dur))
        alpha = int(180 * (1 - frac))
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        s.fill((220, 40, 40, alpha))
        surf.blit(s, (0,0))

# ---------------- 生成谱面 ----------------
def spawn_schedule(level, lane_ys):
    bpm = level["bpm"]; beat_sec = 60.0/bpm
    start_x = SCREEN_W + 80
    travel = (start_x - HIT_LINE_X) / NOTE_SPEED
    schedule = []
    for beat,lane in level["pattern"]:
        t = beat*beat_sec
        schedule.append(dict(spawn=max(0.0, t-travel), lane=lane))
    return schedule

# ---------------- 主程序 ----------------
def main():
    global LANE_SOUNDS, MUTED
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=512)
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Rhythm Duck – PFAD A3")
    clock = pygame.time.Clock()

    # 预生成三条轨的音色
    LANE_SOUNDS = [sine_sound(f, 0.18, VOL_MASTER) for f in LANE_FREQS]

    # UI 按钮
    btn_mute = pygame.Rect(SCREEN_W-120, 20, 100, 36)
    btn_start = pygame.Rect(SCREEN_W//2-70, SCREEN_H//2+20, 140, 44)
    btn_exit = pygame.Rect(SCREEN_W-120, SCREEN_H-60, 100, 36)

    # 状态
    state = "menu"          # menu / select / playing / fail / pass
    unlocked = 1            # 已解锁关卡数（至少 1）
    level_idx = 0
    lane_ys = lane_ys_for(LEVELS[0]["lanes"])
    duck = Duck(lane_ys)

    # 关卡运行变量
    hp = MAX_HP
    t_elapsed = 0.0
    upcoming = []           # [{spawn, lane}]
    active_notes = []
    effects = []            # visual/audio effects (HitEffect, TextPop, MissFlash)

    def start_level(idx):
        nonlocal hp, t_elapsed, upcoming, active_notes, lane_ys
        nonlocal effects
        L = LEVELS[idx]
        lane_ys = lane_ys_for(L["lanes"])
        duck.set_lanes(lane_ys)
        hp = MAX_HP
        t_elapsed = 0.0
        active_notes = []
        upcoming = sorted(spawn_schedule(L, lane_ys), key=lambda d:d["spawn"])
        effects = []
        return L

    level = LEVELS[level_idx]

    # ----------- 主循环 -----------
    while True:
        dt = clock.tick(60)/1000.0
        # ---- input ----
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_q):
                    pygame.quit(); sys.exit(0)
                if e.key == pygame.K_m:
                    MUTED = not MUTED

                # 全局：菜单/选择/结算按键
                if state in ("menu","select","fail","pass"):
                    if e.key in (pygame.K_SPACE, pygame.K_DELETE):
                        if state == "menu":
                            state = "select"
                        elif state == "select":
                            level = start_level(level_idx)
                            state = "playing"
                        elif state == "fail":
                            level = start_level(level_idx)
                            state = "playing"
                        elif state == "pass":
                            state = "select"

                # 游玩中
                if state == "playing":
                    if e.key in (pygame.K_w, pygame.K_UP): duck.up()
                    if e.key in (pygame.K_s, pygame.K_DOWN): duck.down()

            if e.type == pygame.MOUSEBUTTONDOWN:
                if btn_mute.collidepoint(e.pos):
                    MUTED = not MUTED
                elif state == "menu" and btn_start.collidepoint(e.pos):
                    state = "select"
                elif state == "playing" and btn_exit.collidepoint(e.pos):
                    state = "select"

        # ---- update ----
        if state == "playing":
            t_elapsed += dt

            # 生成音符
            while upcoming and upcoming[0]["spawn"] <= t_elapsed:
                info = upcoming.pop(0)
                lane = info["lane"]
                y = lane_ys[lane]
                active_notes.append(Note(SCREEN_W+80, lane, y, NOTE_SPEED, min(lane,2)))

            # 移动、判定
            for n in active_notes: n.update(dt)

            for n in active_notes:
                if not n.hit and not n.missed and n.lane_idx == duck.idx:
                    if abs(n.x - HIT_LINE_X) <= HIT_WINDOW:
                        n.hit = True
                        duck.eat()
                        if not MUTED:
                            LANE_SOUNDS[n.freq_idx].play()
                        # spawn a small hit effect and floating text
                        effects.append(HitEffect(n.x, n.y))
                        effects.append(TextPop(n.x, n.y, "HIT!", color=(255,240,200)))

            # Miss 扣血（仅扣一次）
            for n in active_notes:
                if n.missed:
                    hp -= HP_MISS
                    n.missed = False
                    effects.append(MissFlash())

            # 清理离场的音符
            active_notes = [n for n in active_notes if n.x > -50 and not (n.hit and n.x < HIT_LINE_X-60)]

            duck.update(dt)
            # 胜负判断
            if hp <= 0:
                state = "fail"
            elif not upcoming and not active_notes:
                state = "pass"
                unlocked = max(unlocked, min(level_idx+2, len(LEVELS)))

        # update effects (run regardless of state)
        for ef in effects:
            ef.update(dt)
        effects = [ef for ef in effects if ef.alive()]

        # ---- draw ----
        draw_bg(screen, lane_ys)
        draw_button(screen, btn_mute, "MUSIC" if not MUTED else "MUTE", active=not MUTED)
        draw_hp(screen, hp if state=="playing" else MAX_HP)
        if state == "playing":
            draw_button(screen, btn_exit, "EXIT")

        # 音符 & 小鸭
        for n in active_notes:
            n.draw(screen)
        duck.draw(screen)

        # 特效（在音符/小鸭之后绘制，便于覆盖）
        for ef in effects:
            ef.draw(screen)

        # 顶部标题/提示
        if state == "menu":
            text(screen, "Rhythm Duck", (SCREEN_W//2, 150), 56, (30,60,100), center=True)
            text(screen, "W/S or ↑/↓ to move • Space/Delete to start • M mute • Esc quit",
                 (SCREEN_W//2, 210), 24, (50,70,90), center=True)
            draw_button(screen, btn_start, "START")
        elif state == "select":
            text(screen, "Select Level", (SCREEN_W//2, 110), 44, (30,60,100), center=True)
            # 画三个关卡按钮（解锁控制）
            btns=[]
            for i,L in enumerate(LEVELS):
                rect=pygame.Rect(SCREEN_W//2-240+ i*160, 220, 140, 60)
                btns.append((rect,i))
                unlocked_flag = (i < unlocked)
                draw_button(screen, rect, f"{i+1}. {L['name'].split('–')[0].strip()}", active=unlocked_flag)
                if unlocked_flag and pygame.mouse.get_pressed()[0] and rect.collidepoint(pygame.mouse.get_pos()):
                    level_idx = i
                    level = start_level(level_idx)
                    state = "playing"
            text(screen, "Space/Delete to play selected level", (SCREEN_W//2, 320+80), 22, (70,90,110), center=True)

        elif state == "playing":
            text(screen, f"{level['name']}  |  BPM {level['bpm']}  |  Lanes {level['lanes']}",
                 (24, 20), 26, (30,60,90))

        elif state == "fail":
            text(screen, "Stage Failed", (SCREEN_W//2, 160), 52, (210,60,50), center=True)
            text(screen, "Press Space/Delete to retry  •  Esc to quit  •  M to mute",
                 (SCREEN_W//2, 220), 24, (70,90,110), center=True)

        elif state == "pass":
            cleared_all = (unlocked == len(LEVELS))
            msg = "All Levels Cleared!" if cleared_all else "Stage Cleared!"
            col = (60,140,80)
            text(screen, msg, (SCREEN_W//2, 160), 52, col, center=True)
            text(screen, "Press Space/Delete to go to Level Select",
                 (SCREEN_W//2, 220), 24, (70,90,110), center=True)

        pygame.display.flip()

if __name__ == "__main__":
    pygame.mixer.pre_init(SR, size=16, channels=2, buffer=512)
    main()
