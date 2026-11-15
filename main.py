#!/usr/bin/env python3
"""ai-excited-01: "KURA TERBANG!" -- a superhero turtle mid-leap.

Procedural raster image, standard library only, fully deterministic:
running it twice produces byte-identical PNG output.

Scene: a big superhero turtle leaps diagonally across a purple-orange
sunset, red cape streaming, tiny aviator goggles, flame-patterned shell,
speed lines and a starburst ring around it. Below, a tiny snail spectator
holds a stopwatch, stunned -- the joke is that the "slow" rival is the
witness. One huge central figure, high-saturation contrast, reads clearly
even at ~300 px. No text anywhere, so nothing can come out garbled.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- framebuffer
# One bytearray per row, RGB. All drawing is span-based (slice assignment)
# so a 1024x1024 render stays fast in pure Python.
fb = [bytearray(W * 3) for _ in range(H)]


def _clip_x(x0, x1):
    x0 = max(0, int(x0))
    x1 = min(W, int(x1))
    return x0, x1


def hspan(y, x0, x1, rgb):
    """Fill a horizontal run of row y with one opaque colour."""
    if y < 0 or y >= H:
        return
    x0, x1 = _clip_x(x0, x1)
    if x1 <= x0:
        return
    row = fb[y]
    row[x0 * 3:x1 * 3] = bytes(rgb) * (x1 - x0)


def lerp(a, b, t):
    return int(round(a + (b - a) * t))


def mix(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def vgrad(y, stops):
    """Vertical gradient colour at row y; stops = [(pos0..1, rgb), ...]."""
    t = y / (H - 1)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return mix(c0, c1, f)
    return stops[-1][1]


def fill_ellipse(cx, cy, rx, ry, rgb):
    """Filled ellipse, axis-aligned."""
    if rx <= 0 or ry <= 0:
        return
    y0 = max(0, int(math.ceil(cy - ry)))
    y1 = min(H - 1, int(math.floor(cy + ry)))
    for y in range(y0, y1 + 1):
        dy = (y - cy) / ry
        d = 1.0 - dy * dy
        if d < 0:
            continue
        dx = rx * math.sqrt(d)
        hspan(y, cx - dx, cx + dx + 1, rgb)


def fill_circle(cx, cy, r, rgb):
    fill_ellipse(cx, cy, r, r, rgb)


def fill_poly(points, rgb):
    """Scanline polygon fill (even-odd via sorted intersections)."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, int(math.ceil(min(ys))))
    y1 = min(H - 1, int(math.floor(max(ys))))
    n = len(points)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, y0p = points[i]
            x1, y1p = points[(i + 1) % n]
            if y0p == y1p:
                continue
            if (y0p <= y < y1p) or (y1p <= y < y0p):
                xs.append(x0 + (y - y0p) * (x1 - x0) / (y1p - y0p))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            hspan(y, xs[i], xs[i + 1] + 1, rgb)


def thick_line(x0, y0, x1, y1, w, rgb):
    """Thick line with round caps, drawn as stamped circles."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length == 0:
        fill_circle(x0, y0, w / 2, rgb)
        return
    steps = max(2, int(length / max(2.0, w / 3.0)) + 1)
    r = w / 2
    for i in range(steps + 1):
        t = i / steps
        fill_circle(x0 + dx * t, y0 + dy * t, r, rgb)


def arc_points(cx, cy, r, a0, a1, n=24):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def thick_arc(cx, cy, r, a0, a1, w, rgb):
    pts = arc_points(cx, cy, r, a0, a1)
    for i in range(len(pts) - 1):
        thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w, rgb)


def star_points(cx, cy, r_out, r_in, spikes, rot=-math.pi / 2):
    pts = []
    for i in range(spikes * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot + i * math.pi / spikes
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def sparkle(cx, cy, r, rgb):
    """Small 4-point star."""
    fill_poly([(cx, cy - r), (cx + r * 0.28, cy - r * 0.28),
               (cx + r, cy), (cx + r * 0.28, cy + r * 0.28),
               (cx, cy + r), (cx - r * 0.28, cy + r * 0.28),
               (cx - r, cy), (cx - r * 0.28, cy - r * 0.28)], rgb)


# ------------------------------------------------------------------- palette
SKY = [(0.00, (38, 12, 84)), (0.38, (122, 32, 140)),
       (0.62, (226, 62, 110)), (0.80, (255, 128, 48)),
       (1.00, (255, 196, 90))]
SUN_CORE = (255, 244, 190)
SUN_MID = (255, 214, 90)
SUN_OUT = (255, 150, 60)
STAR_YELLOW = (255, 214, 64)
STAR_WHITE = (255, 246, 200)
CAPE = (224, 38, 38)
CAPE_DARK = (158, 18, 28)
CAPE_LIGHT = (255, 92, 74)
SHELL = (34, 139, 58)
SHELL_DARK = (16, 84, 38)
SHELL_LIGHT = (74, 184, 92)
BELLY = (216, 240, 150)
SKIN = (96, 196, 96)
SKIN_DARK = (52, 140, 66)
FLAME_Y = (255, 214, 64)
FLAME_O = (255, 122, 26)
FLAME_R = (230, 57, 40)
GOLD = (255, 196, 66)
LENS = (26, 26, 46)
WHITE = (255, 255, 255)
INK = (24, 12, 40)
GROUND = (26, 10, 48)
SNAIL_BODY = (255, 214, 165)
SNAIL_SHELL = (151, 117, 250)
SNAIL_SHELL_DARK = (104, 72, 200)

SUN_CX, SUN_CY = 560, 430


def draw():
    # ---- sky: vertical sunset gradient -------------------------------
    for y in range(H):
        hspan(y, 0, W, vgrad(y, SKY))

    # ---- distant stars in the purple top -----------------------------
    for (sx, sy, sr) in [(90, 70, 7), (210, 140, 5), (330, 60, 6),
                         (760, 90, 6), (880, 170, 5), (950, 60, 7),
                         (480, 110, 5), (620, 55, 4), (150, 230, 4),
                         (920, 300, 4)]:
        sparkle(sx, sy, sr, (255, 240, 200))

    # ---- sun glow: concentric discs, brightest in the middle ---------
    for r, c in [(400, (255, 122, 40)), (330, (255, 158, 52)),
                 (270, (255, 186, 66)), (210, (255, 208, 84)),
                 (160, SUN_MID), (115, SUN_CORE)]:
        fill_circle(SUN_CX, SUN_CY, r, c)

    # ---- sun rays: alternating lighter wedges ------------------------
    for k in range(12):
        a0 = k * math.pi / 6 + 0.10
        a1 = a0 + 0.10
        fill_poly([(SUN_CX, SUN_CY),
                   (SUN_CX + 440 * math.cos(a0), SUN_CY + 440 * math.sin(a0)),
                   (SUN_CX + 440 * math.cos(a1), SUN_CY + 440 * math.sin(a1))],
                  (255, 190, 80))

    # ---- diagonal speed lines, back layer ----------------------------
    for (x0, y0, x1, y1, w, c) in [
            (60, 180, 420, 60, 10, (255, 255, 255)),
            (700, 120, 990, 30, 8, (255, 240, 170)),
            (40, 700, 300, 610, 9, (255, 220, 140)),
            (760, 760, 990, 680, 10, (255, 255, 255)),
            (120, 420, 330, 360, 7, (255, 240, 170)),
            (880, 480, 1000, 440, 7, (255, 220, 140))]:
        thick_line(x0, y0, x1, y1, w, c)

    # ---- starburst ring behind the turtle ----------------------------
    fill_poly(star_points(500, 470, 345, 268, 16), STAR_YELLOW)
    fill_poly(star_points(500, 470, 292, 238, 16, rot=-math.pi / 2 + 0.10),
              STAR_WHITE)

    # ---- cape: big flowing shape streaming down-left -----------------
    fill_poly([(430, 420), (300, 470), (150, 550), (60, 710), (150, 690),
               (210, 780), (280, 700), (350, 800), (400, 690), (470, 640),
               (520, 560), (500, 470)], CAPE)
    # cape shading + bright fold
    fill_poly([(430, 420), (300, 470), (190, 540), (130, 650), (200, 620),
               (300, 560), (420, 500)], CAPE_DARK)
    fill_poly([(470, 470), (380, 560), (330, 660), (380, 640), (440, 560)],
              CAPE_LIGHT)
    # cape clasp
    fill_circle(445, 445, 22, GOLD)
    fill_circle(445, 445, 12, (255, 230, 140))

    # ---- back legs trailing (behind shell) ---------------------------
    thick_line(360, 600, 250, 690, 46, SKIN_DARK)
    thick_line(400, 640, 300, 740, 44, SKIN)
    fill_ellipse(245, 695, 52, 30, SKIN)
    fill_ellipse(295, 745, 50, 28, SKIN_DARK)

    # ---- tail ---------------------------------------------------------
    fill_poly([(300, 560), (240, 600), (305, 610)], SKIN_DARK)

    # ---- shell: dark rim, green body ----------------------------------
    fill_ellipse(500, 480, 235, 195, SHELL_DARK)
    fill_ellipse(500, 480, 218, 180, SHELL)
    # shell scutes: lighter arcs
    thick_arc(500, 480, 150, math.pi * 0.95, math.pi * 1.85, 10, SHELL_LIGHT)
    thick_arc(500, 480, 95, math.pi * 1.05, math.pi * 1.75, 8, SHELL_LIGHT)
    # flame / rocket pattern on the shell (kept clear of the belly)
    fill_poly([(420, 560), (455, 470), (490, 560), (470, 520), (450, 560)],
              FLAME_O)
    fill_poly([(470, 430), (505, 350), (540, 430), (520, 395), (495, 430)],
              FLAME_Y)
    fill_poly([(560, 420), (585, 350), (610, 420), (595, 390), (580, 420)],
              FLAME_R)
    fill_poly([(380, 470), (405, 400), (432, 470), (418, 440), (400, 470)],
              FLAME_Y)

    # ---- belly ---------------------------------------------------------
    fill_ellipse(575, 555, 135, 95, BELLY)
    thick_arc(575, 555, 98, math.pi * 0.15, math.pi * 0.85, 8, (190, 220, 110))

    # ---- front legs stretched forward like Superman (drawn before the
    # ---- head, but long enough to stick out past it, upper-right) -----
    thick_line(700, 400, 900, 320, 52, SKIN)
    thick_line(680, 500, 890, 470, 50, SKIN_DARK)
    fill_ellipse(905, 318, 46, 30, SKIN)      # front foot
    fill_ellipse(895, 468, 44, 28, SKIN_DARK)  # front foot

    # ---- head ----------------------------------------------------------
    fill_circle(700, 330, 98, SKIN)
    fill_ellipse(760, 360, 62, 48, SKIN)      # snout
    # smile
    thick_arc(745, 345, 34, math.pi * 0.15, math.pi * 0.85, 9, INK)
    # cheek blush
    fill_ellipse(688, 408, 26, 15, (255, 140, 120))
    # aviator goggles: gold rims, dark lenses, strap
    thick_line(610, 300, 790, 285, 14, GOLD)
    fill_ellipse(655, 300, 46, 40, GOLD)
    fill_ellipse(760, 292, 46, 40, GOLD)
    fill_ellipse(655, 300, 36, 30, LENS)
    fill_ellipse(760, 292, 36, 30, LENS)
    fill_ellipse(645, 290, 10, 8, WHITE)      # lens glints
    fill_ellipse(750, 282, 10, 8, WHITE)

    # ---- foreground speed lines ---------------------------------------
    for (x0, y0, x1, y1, w, c) in [
            (30, 300, 260, 240, 9, (255, 255, 255)),
            (820, 180, 1000, 130, 9, (255, 240, 170)),
            (60, 880, 260, 820, 8, (255, 220, 140)),
            (860, 880, 1000, 840, 8, (255, 255, 255))]:
        thick_line(x0, y0, x1, y1, w, c)

    # ---- sparkles around the burst -------------------------------------
    for (sx, sy, sr) in [(180, 300, 16), (850, 320, 18), (830, 640, 14),
                         (200, 620, 13), (620, 130, 15), (380, 820, 12),
                         (930, 560, 12)]:
        sparkle(sx, sy, sr, (255, 250, 210))

    # ---- ground: dark hill + motion streaks ----------------------------
    fill_ellipse(512, 1080, 700, 130, GROUND)
    for (x0, y0, x1, y1, w, c) in [
            (120, 960, 420, 930, 8, (255, 200, 100)),
            (620, 970, 920, 940, 8, (255, 220, 140)),
            (300, 1000, 560, 980, 7, (255, 240, 170))]:
        thick_line(x0, y0, x1, y1, w, c)

    # ---- the snail spectator, bottom-left ------------------------------
    # eye stalks + wide stunned eyes
    thick_line(150, 880, 138, 830, 7, SNAIL_BODY)
    thick_line(180, 878, 178, 826, 7, SNAIL_BODY)
    fill_circle(136, 824, 16, WHITE)
    fill_circle(178, 820, 16, WHITE)
    fill_circle(138, 826, 7, INK)
    fill_circle(180, 822, 7, INK)
    # body
    fill_ellipse(185, 905, 95, 42, SNAIL_BODY)
    # shell with spiral
    fill_circle(215, 870, 62, SNAIL_SHELL_DARK)
    fill_circle(215, 870, 54, SNAIL_SHELL)
    thick_arc(215, 870, 38, 0.0, math.pi * 1.5, 9, SNAIL_SHELL_DARK)
    thick_arc(215, 870, 22, math.pi * 0.5, math.pi * 2.0, 8, SNAIL_SHELL_DARK)
    fill_circle(215, 870, 8, SNAIL_SHELL_DARK)
    # open stunned mouth
    fill_ellipse(140, 895, 12, 16, INK)
    # sweat drop of disbelief
    fill_poly([(110, 800), (122, 824), (98, 824)], (140, 200, 255))
    fill_circle(110, 824, 12, (140, 200, 255))
    # stopwatch held up in its "hand"
    thick_line(270, 890, 300, 850, 8, SNAIL_BODY)
    fill_circle(308, 838, 30, GOLD)
    fill_circle(308, 838, 24, WHITE)
    thick_line(308, 838, 308, 820, 5, INK)
    thick_line(308, 838, 322, 846, 5, INK)
    fill_circle(308, 838, 4, INK)
    thick_line(308, 808, 308, 800, 6, GOLD)  # winder button

    # ---- tiny snail trail dots (it barely moved) -----------------------
    for (tx, ty, tr) in [(330, 940, 6), (360, 946, 5), (390, 950, 4)]:
        fill_circle(tx, ty, tr, (255, 255, 255))


# ---------------------------------------------------------------------- PNG
def chunk(ctype, data):
    out = struct.pack(">I", len(data)) + ctype + data
    out += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += fb[y]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


def main():
    draw()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(encode_png())
    print("wrote", path)


if __name__ == "__main__":
    main()
