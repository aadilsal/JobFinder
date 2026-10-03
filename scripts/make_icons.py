"""Generate the PWA icons in web/icons/ with no image libraries:  python scripts/make_icons.py"""
import struct, zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "web" / "icons"
TOP, BOTTOM = (59, 130, 246), (29, 78, 216)   # blue gradient
WHITE = (255, 255, 255)


def rrect(u, v, x0, y0, x1, y1, r):
    if not (x0 <= u <= x1 and y0 <= v <= y1):
        return False
    cx = min(max(u, x0 + r), x1 - r)
    cy = min(max(v, y0 + r), y1 - r)
    return (u - cx) ** 2 + (v - cy) ** 2 <= r * r


def briefcase(u, v):
    """Glyph in its own 0..1 box: True where the white briefcase is."""
    handle = rrect(u, v, .33, .10, .67, .36, .09) and not rrect(u, v, .42, .19, .58, .40, .03)
    body = rrect(u, v, .06, .30, .94, .88, .10)
    seam = .53 <= v <= .58 and not (.43 <= u <= .57)
    clasp = rrect(u, v, .43, .47, .57, .64, .03)
    return handle or (body and not seam) or clasp


def render(size, glyph_box, bg="rounded", ss=3):
    g0, g1 = glyph_box
    rows = []
    for y in range(size):
        row = bytearray(b"\x00")
        for x in range(size):
            acc = [0, 0, 0, 0]
            for sy in range(ss):
                for sx in range(ss):
                    u, v = (x + (sx + .5) / ss) / size, (y + (sy + .5) / ss) / size
                    gu, gv = (u - g0) / (g1 - g0), (v - g0) / (g1 - g0)
                    on_bg = bg == "square" or (bg == "rounded" and rrect(u, v, 0, 0, 1, 1, .22))
                    col = tuple(int(a + (b - a) * v) for a, b in zip(TOP, BOTTOM))
                    if 0 <= gu <= 1 and 0 <= gv <= 1 and briefcase(gu, gv):
                        px = (*WHITE, 255)
                    elif on_bg:
                        px = (*col, 255)
                    else:
                        px = (0, 0, 0, 0)
                    for i in range(3):
                        acc[i] += px[i] * px[3]
                    acc[3] += px[3]
            rgb = [int(acc[i] / acc[3]) if acc[3] else 0 for i in range(3)]
            row += bytes(rgb + [int(acc[3] / (ss * ss))])
        rows.append(bytes(row))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, box, bg in [("icon-192.png", 192, (.22, .78), "rounded"), ("icon-512.png", 512, (.22, .78), "rounded"),
                                ("maskable-512.png", 512, (.28, .72), "square"), ("apple-touch-icon.png", 180, (.2, .8), "square"),
                                ("badge-96.png", 96, (.08, .92), "none")]:
        (OUT / name).write_bytes(render(size, box, bg, ss=2 if size > 200 else 3))
        print("wrote", OUT / name)
