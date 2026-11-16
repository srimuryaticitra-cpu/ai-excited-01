# KURA TERBANG! — The Tortoise That Launches Itself
# ai-excited-01 entry: a deterministic program that paints one image.
# Pure Python standard library only, no network, no randomness at run time.
# Run:  python3 main.py        -> writes /output/entry.png (1024x1024, < 1 MiB)
import os
import struct
import zlib

W, H = 1024, 1024
OUT = "/output/entry.png"


# ---------------------------------------------------------------- deterministic rng
class Rng:
    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFF

    def next(self):
        self.s = (1664525 * self.s + 1013904223) & 0xFFFFFFFF
        return self.s

    def range(self, lo, hi):
        return lo + self.next() % (hi - lo + 1)

    def pick(self, items):
        return items[self.next() % len(items)]


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def blend(self, x, y, c, a):
        # a in 0..255, draw colour c over what is already there
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            inv = 255 - a
            self.px[i] = (c[0] * a + self.px[i] * inv) // 255
            self.px[i + 1] = (c[1] * a + self.px[i + 1] * inv) // 255
            self.px[i + 2] = (c[2] * a + self.px[i + 2] * inv) // 255

    def hline(self, x0, x1, y, c):
        if y < 0 or y >= self.h:
            return
        x0, x1 = max(0, x0), min(self.w - 1, x1)
        for x in range(x0, x1 + 1):
            self.set(x, y, c)

    def vline(self, x, y0, y1, c):
        if x < 0 or x >= self.w:
            return
        y0, y1 = max(0, y0), min(self.h - 1, y1)
        for y in range(y0, y1 + 1):
            self.set(x, y, c)

    def line(self, x0, y0, x1, y1, c, thick=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            for ox in range(-thick // 2, thick // 2 + 1):
                for oy in range(-thick // 2, thick // 2 + 1):
                    self.set(x0 + ox, y0 + oy, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c):
        for y in range(cy - r, cy + r + 1):
            dx = int((r * r - (y - cy) * (y - cy)) ** 0.5) if abs(y - cy) <= r else 0
            self.hline(cx - dx, cx + dx, y, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for y in range(cy - ry, cy + ry + 1):
            t = 1.0 - ((y - cy) / ry) ** 2
            dx = int(rx * (t ** 0.5)) if t > 0 else 0
            self.hline(cx - dx, cx + dx, y, c)

    def poly(self, pts, c):
        # scanline fill of a simple polygon
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h - 1, max(ys)) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    xs.append(x)
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline(int(xs[i]), int(xs[i + 1]), y, c)

    def ring(self, cx, cy, r0, r1, c):
        for y in range(cy - r1, cy + r1 + 1):
            dy = y - cy
            if abs(dy) > r1:
                continue
            dx1 = int((r1 * r1 - dy * dy) ** 0.5)
            dx0 = int((r0 * r0 - dy * dy) ** 0.5) if abs(dy) <= r0 else 0
            self.hline(cx - dx1, cx - dx0, y, c)
            self.hline(cx + dx0, cx + dx1, y, c)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------------------------------------------------------------- palette
INDIGO = (26, 16, 66)
PURPLE = (88, 32, 120)
MAGENTA = (196, 52, 120)
ORANGE = (255, 138, 61)
GOLD = (255, 196, 66)
CREAM = (255, 240, 205)
SHELL = (46, 125, 50)
SHELL_D = (27, 85, 34)
SHELL_L = (104, 183, 84)
SKIN = (232, 190, 120)
SKIN_D = (198, 148, 82)
RED = (214, 48, 49)
WHITE = (255, 255, 255)
BLACK = (20, 16, 24)
FLAME_Y = (255, 214, 64)
FLAME_O = (255, 122, 26)
FLAME_R = (230, 57, 25)


def draw(c):
    rng = Rng(20261116)

    # --- sky gradient: indigo top -> purple -> magenta -> orange horizon
    stops = [(0.0, INDIGO), (0.38, PURPLE), (0.68, MAGENTA), (1.0, ORANGE)]
    for y in range(H):
        t = y / (H - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                col = lerp(c0, c1, (t - t0) / (t1 - t0))
                break
        else:
            col = ORANGE
        c.hline(0, W - 1, y, col)

    # --- stars in the upper sky
    for _ in range(180):
        x = rng.range(0, W - 1)
        y = rng.range(0, 420)
        s = rng.pick([1, 1, 1, 2])
        a = rng.range(120, 255)
        for ox in range(s):
            for oy in range(s):
                c.blend(x + ox, y + oy, WHITE, a)

    # --- glowing portal ring behind the tortoise
    cx, cy = 512, 500
    for r, col, a in ((330, GOLD, 26), (300, GOLD, 40), (272, CREAM, 60)):
        for k in range(360):
            import math
            ang = math.radians(k)
            x = int(cx + r * math.cos(ang))
            y = int(cy + r * math.sin(ang))
            c.blend(x, y, col, a)
            c.blend(x + 1, y, col, a)
    c.ring(cx, cy, 258, 268, GOLD)

    # --- distant hills
    c.ellipse(180, 980, 420, 130, (58, 28, 84))
    c.ellipse(860, 1000, 460, 140, (48, 22, 72))
    c.ellipse(512, 1060, 700, 150, (38, 18, 60))

    # --- launch pad smoke puffs at the bottom
    for i in range(9):
        px = 300 + i * 52 + rng.range(-14, 14)
        py = 930 + rng.range(-18, 18)
        pr = rng.range(26, 52)
        c.circle(px, py, pr, (255, 226, 190))
        c.circle(px - 8, py - 10, pr - 12, (255, 244, 224))

    # --- rocket flame (layered teardrops, pointing down-left)
    fx, fy = 380, 640
    c.poly([(fx + 40, fy - 30), (fx - 60, fy + 150), (fx + 130, fy + 190),
            (fx + 170, fy + 40)], FLAME_R)
    c.poly([(fx + 55, fy - 20), (fx - 10, fy + 110), (fx + 115, fy + 140),
            (fx + 145, fy + 30)], FLAME_O)
    c.poly([(fx + 70, fy - 10), (fx + 35, fy + 70), (fx + 100, fy + 90),
            (fx + 120, fy + 20)], FLAME_Y)
    c.circle(fx + 78, fy + 30, 26, (255, 246, 200))
    # sparks
    for _ in range(40):
        sx = fx + rng.range(-40, 180)
        sy = fy + rng.range(60, 260)
        c.circle(sx, sy, rng.pick([2, 2, 3]), rng.pick([GOLD, FLAME_O, CREAM]))

    # --- speed lines
    for _ in range(26):
        x0 = rng.range(40, 980)
        y0 = rng.range(120, 880)
        ln = rng.range(60, 190)
        c.line(x0, y0, x0 - ln, y0 + ln // 4, WHITE, thick=3)

    # --- tortoise, tilted: shell dome, head, helmet, legs
    # shell (big dome)
    c.ellipse(540, 520, 250, 185, SHELL_D)
    c.ellipse(540, 510, 238, 172, SHELL)
    # shell plates
    c.ellipse(470, 470, 62, 48, SHELL_L)
    c.ellipse(600, 450, 58, 44, SHELL_L)
    c.ellipse(540, 560, 66, 46, SHELL_L)
    c.ellipse(660, 540, 52, 40, SHELL_L)
    c.ellipse(440, 560, 50, 38, SHELL_L)
    # shell rim highlight
    c.ring(540, 515, 226, 238, SHELL_L)

    # head, stretched forward and up
    c.ellipse(760, 400, 92, 66, SKIN)
    c.ellipse(742, 392, 78, 54, (244, 205, 140))
    # snout + smile
    c.ellipse(828, 420, 34, 24, SKIN)
    c.line(818, 436, 852, 428, BLACK, thick=4)
    c.circle(838, 402, 5, BLACK)  # nostril
    # big determined eye
    c.circle(758, 372, 26, WHITE)
    c.circle(766, 372, 13, BLACK)
    c.circle(770, 368, 5, WHITE)
    # raised eyebrow
    c.line(728, 336, 782, 330, BLACK, thick=6)
    # red helmet with goggles
    c.ellipse(736, 348, 96, 58, RED)
    c.ellipse(736, 356, 96, 44, (232, 64, 60))
    c.circle(736, 306, 14, GOLD)  # helmet button
    c.line(700, 372, 800, 366, (40, 40, 60), thick=10)  # goggle strap
    c.circle(726, 370, 20, (140, 210, 235))  # goggle lens
    c.circle(786, 366, 20, (140, 210, 235))
    c.circle(726, 370, 12, (200, 235, 250))
    c.circle(786, 366, 12, (200, 235, 250))
    # helmet spike
    c.poly([(700, 306), (736, 240), (772, 306)], GOLD)

    # front leg reaching forward, back legs tucked
    c.ellipse(700, 640, 58, 34, SKIN_D)
    c.ellipse(716, 646, 44, 24, SKIN)
    c.ellipse(430, 660, 52, 30, SKIN_D)
    c.ellipse(420, 664, 38, 20, SKIN)
    c.ellipse(560, 690, 56, 30, SKIN_D)
    # tail
    c.poly([(330, 560), (290, 540), (296, 580), (336, 586)], SKIN_D)

    # cape! a tiny red cape fluttering behind the shell
    c.poly([(340, 470), (210, 420), (180, 520), (300, 540)], (178, 32, 40))
    c.poly([(340, 480), (230, 440), (210, 510), (300, 530)], RED)

    # --- confetti
    confetti_cols = [GOLD, (120, 220, 255), (255, 110, 180), (140, 255, 170), WHITE]
    for _ in range(90):
        x = rng.range(30, 990)
        y = rng.range(60, 940)
        col = rng.pick(confetti_cols)
        if rng.next() % 2:
            c.circle(x, y, rng.pick([3, 4, 5]), col)
        else:
            c.poly([(x, y), (x + 9, y + 3), (x + 5, y + 10), (x - 3, y + 6)], col)

    # --- funny detail: shocked bird with a party hat, top-left
    bx, by = 150, 150
    c.ellipse(bx, by, 46, 40, (240, 244, 250))  # body
    c.circle(bx + 30, by - 28, 26, (240, 244, 250))  # head
    c.circle(bx + 38, by - 34, 9, WHITE)  # wide eye
    c.circle(bx + 40, by - 34, 4, BLACK)
    c.circle(bx + 18, by - 34, 9, WHITE)
    c.circle(bx + 20, by - 34, 4, BLACK)
    c.poly([(bx + 52, by - 22), (bx + 78, by - 18), (bx + 54, by - 8)], (255, 170, 40))  # open beak
    c.poly([(bx + 8, by - 50), (bx + 30, by - 96), (bx + 48, by - 48)], (255, 80, 120))  # party hat
    c.circle(bx + 30, by - 96, 7, GOLD)
    c.line(bx - 20, by + 30, bx - 44, by + 52, (200, 120, 60), thick=5)  # wing
    # bird's dropped popcorn
    for i in range(6):
        c.circle(bx + 30 + i * 12, by + 90 + i * 8, 5, CREAM)

    # --- tiny snail on the hill with a GO flag, bottom-right
    sx, sy = 880, 900
    c.ellipse(sx, sy, 40, 30, SKIN)
    c.circle(sx + 34, sy - 26, 22, (200, 90, 90))
    c.ring(sx + 34, sy - 26, 8, 20, (240, 180, 120))
    c.circle(sx + 52, sy - 44, 5, BLACK)
    c.line(sx + 52, sy - 44, sx + 58, sy - 60, BLACK, thick=3)
    c.line(sx + 46, sy - 44, sx + 44, sy - 60, BLACK, thick=3)
    c.line(sx + 10, sy - 20, sx + 10, sy - 66, BLACK, thick=4)
    c.poly([(sx + 10, sy - 66), (sx + 52, sy - 56), (sx + 10, sy - 46)], (60, 200, 90))


# ---------------------------------------------------------------- png encode
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def save_png(c, path):
    raw = bytearray()
    for y in range(c.h):
        raw.append(0)  # filter: none
        raw += c.px[y * c.w * 3:(y + 1) * c.w * 3]
    ihdr = struct.pack(">IIBBBBB", c.w, c.h, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def main():
    c = Canvas(W, H)
    draw(c)
    save_png(c, OUT)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
