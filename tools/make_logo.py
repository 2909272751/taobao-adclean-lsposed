#!/usr/bin/env python3
"""Generate the module logo (original artwork, drawn from primitives).

Design: rounded-square in Taobao orange -> Idlefish amber gradient, a white
shield outline (protection), and inside it a white "banner" block crossed by a
diagonal slash (blocked advertising).

Outputs:
  assets/logo/logo-1024.png       repo / README artwork
  assets/logo/logo-192.png        Android launcher icon (xxxhdpi)
  app/res/drawable-nodpi/ic_launcher.png
"""
from PIL import Image, ImageDraw
from pathlib import Path

S = 1024
ROOT = Path(__file__).resolve().parents[1]

ORANGE_TOP = (255, 106, 0)
ORANGE_BOTTOM = (255, 45, 0)
AMBER = (255, 209, 0)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_square(size):
    img = Image.new('RGB', (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        # orange -> amber in the lower third keeps the Taobao/Idlefish pairing
        c = lerp(ORANGE_TOP, ORANGE_BOTTOM, t) if t < 0.62 else lerp(ORANGE_BOTTOM, AMBER, (t - 0.62) / 0.38)
        d.line([(0, y), (size, y)], fill=c)
    return img


def rounded_mask(size, radius):
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def shield_polygon(cx, top, bottom, half_w, shoulder):
    """Shield outline: straight shoulders, then a smooth taper to the bottom point."""
    pts = [(cx - half_w, top), (cx + half_w, top), (cx + half_w, top + shoulder)]
    steps = 26
    for i in range(1, steps + 1):
        t = i / steps
        # quadratic-ish taper so the lower half reads as a shield, not a hexagon
        w = half_w * (1.0 - t * t * 0.98)
        y = top + shoulder + (bottom - top - shoulder) * t
        pts.append((cx + w, y))
    for i in range(steps - 1, -1, -1):
        t = i / steps
        w = half_w * (1.0 - t * t * 0.98)
        y = top + shoulder + (bottom - top - shoulder) * t
        pts.append((cx - w, y))
    return pts


def draw_logo():
    img = gradient_square(S).convert('RGBA')
    d = ImageDraw.Draw(img)

    cx = S // 2
    top, bottom = 188, 824
    half_w, shoulder = 286, 176
    pts = shield_polygon(cx, top, bottom, half_w, shoulder)

    # soft drop shadow behind the shield
    shadow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 10, y + 16) for x, y in pts], fill=(120, 30, 0, 90))
    from PIL import ImageFilter
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    # white shield
    d.polygon(pts, fill=(255, 255, 255, 255))

    # inner mark: three orange bars = "ad / content" stack
    bar_x = cx - 150
    for i, (w, h) in enumerate([(300, 40), (224, 40), (140, 40)]):
        y = top + 128 + i * 74
        d.rounded_rectangle([bar_x, y, bar_x + w, y + h], radius=20, fill=ORANGE_TOP + (255,))

    # slash: one clean orange bar across the shield (same hue as the bars, so it
    # reads as "crossed out" without a halo artefact)
    slash = [(cx - 214, top + 66), (cx + 214, bottom - 118)]
    d.line(slash, fill=ORANGE_TOP + (255,), width=94)
    for p in slash:
        d.ellipse([p[0] - 47, p[1] - 47, p[0] + 47, p[1] + 47], fill=ORANGE_TOP + (255,))

    mask = rounded_mask(S, 232)
    out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def main():
    logo = draw_logo()
    (ROOT / 'assets' / 'logo').mkdir(parents=True, exist_ok=True)
    (ROOT / 'app' / 'res' / 'drawable-nodpi').mkdir(parents=True, exist_ok=True)

    big = ROOT / 'assets' / 'logo' / 'logo-1024.png'
    logo.save(big)

    for size, dest in [
        (512, ROOT / 'assets' / 'logo' / 'logo-512.png'),
        (192, ROOT / 'assets' / 'logo' / 'logo-192.png'),
        (192, ROOT / 'app' / 'res' / 'drawable-nodpi' / 'ic_launcher.png'),
        (432, ROOT / 'app' / 'res' / 'drawable-nodpi' / 'ic_launcher_xxxhdpi.png'),
    ]:
        logo.resize((size, size), Image.LANCZOS).save(dest)
        print('wrote', dest)


if __name__ == '__main__':
    main()
