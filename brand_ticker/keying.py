"""Key a one colour mark out of a GitHub avatar.

The result is an alpha mask (Pillow "L" image) cropped to the mark, plus its ink coverage.
Modes:
  auto   pick one of the below from the avatar itself (default)
  diff   pixels that differ from the avatar's own ground colour
  alpha  the transparency itself
  inner  the mark inside a one colour tile or badge (white bird on an orange square)
  dark   only near black pixels
  white  only near white pixels
  solid  the opaque shape with its white parts knocked out
Auto refuses photos, illustrations and gradients (NoMark) rather than print a grey smudge.
"""
from collections import Counter

from PIL import Image, ImageChops, ImageFilter

SIZE = 460
RAMPS = {"diff": (70, 150), "inner": (70, 150), "dark": (150, 215), "white": (200, 240)}
MAX_NOISE = .42    # share of in between pixels a keyed mark may have before it counts as a smudge
MIN_FLAT = .3      # the four most common colours must cover this much of an opaque avatar
MAX_PARTS = 40     # more separate pieces than this is confetti, not a mark
MAX_FINE = .8      # hairlines and line art that turn to grey fuzz at strip size


class NoMark(Exception):
    """The avatar has nothing that reads as a mark (a photo, a gradient, an empty square)."""


def ramp(v, a, b):
    return 0.0 if v <= a else 1.0 if v >= b else (v - a) / (b - a)


def _dist(c, d):
    return ((c[0] - d[0]) ** 2 + (c[1] - d[1]) ** 2 + (c[2] - d[2]) ** 2) ** .5


def _pixels(im):
    flat = getattr(im, "get_flattened_data", None)  # Pillow 12.1 renamed getdata
    return list(flat() if flat else im.getdata())


def _to_l(m, w, h):
    im = Image.new("L", (w, h))
    im.putdata([round(v * 255) for v in m])
    return im


def _border(w, h, band=3):
    for y in range(h):
        if y < band or y >= h - band:
            yield from range(y * w, y * w + w)
        else:
            yield from range(y * w, y * w + band)
            yield from range(y * w + w - band, y * w + w)


def _bbox(m, w, level=.5):
    xs, ys = [], []
    for i, v in enumerate(m):
        if v > level:
            ys.append(i // w)
            xs.append(i % w)
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1) if xs else None


def _fill(m, w, box):
    x0, y0, x1, y1 = box
    return sum(m[y * w + x] for y in range(y0, y1) for x in range(x0, x1)) / ((x1 - x0) * (y1 - y0))


def _fine(im, side=60):
    """How much of the mark dissolves into grey when drawn at strip size."""
    w, h = im.size
    k = side / max(w, h)
    small = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    return noise([v / 255 for v in _pixels(small)])


def noise(m):
    """Share of the inked pixels that sit in between ink and ground. Logos are crisp, photos are not."""
    ink = [v for v in m if v > .12]
    return sum(1 for v in ink if v < .88) / len(ink) if ink else 1.0


def flatness(rgb, alpha):
    """Share of the opaque pixels held by the four most common colours (4 bit bins)."""
    bins = Counter((c[0] >> 4, c[1] >> 4, c[2] >> 4) for c, a in zip(rgb, alpha) if a > 128)
    tot = sum(bins.values())
    return sum(n for _, n in bins.most_common(4)) / tot if tot else 1.0


def is_tile(m, w, h):
    """A filled shape behind the mark: a badge that spans the avatar, or any solid block."""
    box = _bbox(m, w)
    if not box:
        return False
    x0, y0, x1, y1 = box
    fill = _fill(m, w, box)
    spans = (x1 - x0) >= .75 * w and (y1 - y0) >= .75 * h
    block = (x1 - x0) * (y1 - y0) >= .1 * w * h and fill >= .93
    return (spans and fill >= .6) or block


def _tile_colour(rgb, m0, w, h):
    """The badge's own colour, read from a band just inside its edge (past any thin border), and the share
    of that band it covers. A four colour square or a gradient scores low."""
    small = _to_l(m0, w, h).reduce(4).point(lambda v: 255 if v > 128 else 0)
    sw, sh = small.size
    outer = _pixels(small.filter(ImageFilter.MinFilter(9)))   # 16 px in
    inner = _pixels(small.filter(ImageFilter.MinFilter(21)))  # 40 px in
    cols = [rgb[(i // sw) * 4 * w + (i % sw) * 4] for i in range(sw * sh)]
    band = [c for c, o, n in zip(cols, outer, inner) if o and not n] or [c for c, o in zip(cols, outer) if o]
    if not band:
        return None, 0.0
    bins = Counter((c[0] >> 4, c[1] >> 4, c[2] >> 4) for c in band)
    best, score = None, -1
    for b, _ in bins.most_common(6):
        members = [c for c in band if (c[0] >> 4, c[1] >> 4, c[2] >> 4) == b]
        centre = tuple(sum(ch) / len(members) for ch in zip(*members))
        n = sum(1 for c in band if _dist(c, centre) < 50)
        if n > score:
            best, score = centre, n
    return best, score / len(band)


def _inner(rgb, m0, w, h, r):
    """The mark inside a one colour tile, or None if the tile is not one colour or holds nothing."""
    tile, share = _tile_colour(rgb, m0, w, h)
    if tile is None or share < .45:
        return None  # four colour squares, a gradient: not a tile with a mark on it
    core_im = _to_l(m0, w, h).filter(ImageFilter.MinFilter(9))  # stay clear of the tile's anti aliased rim
    core = [v / 255 for v in _pixels(core_im)]
    m1 = [ramp(_dist(c, tile), *r) * k for c, k in zip(rgb, core)]
    cov = sum(m1) / (sum(core) or 1)
    if not .015 <= cov <= .75 or noise(m1) > .3:  # nothing inside, or a gradient keyed against itself
        return None
    return m1, core_im


def _base(rgb, alpha, w, h):
    """First pass: the transparency if the ground is see through, else distance from the ground colour."""
    border = list(_border(w, h))
    if sum(alpha[i] < 128 for i in border) > .5 * len(border):
        return [a / 255 for a in alpha], "alpha"
    opaque = sorted((rgb[i] for i in border if alpha[i] >= 128), key=sum)
    bg = opaque[len(opaque) // 2]
    a0, a1 = RAMPS["diff"]
    return [ramp(_dist(c, bg), a0, a1) * a / 255 for c, a in zip(rgb, alpha)], "diff"


def choose(rgb, alpha, w, h):
    """Return (mask, mode, tile) for the avatar, chosen automatically. tile is the badge core for inner."""
    m0, mode = _base(rgb, alpha, w, h)
    if is_tile(m0, w, h):
        got = _inner(rgb, m0, w, h, RAMPS["inner"])
        if got:
            return got[0], "inner", got[1]
    return m0, mode, None


def _components(bits, w, h):
    """4 connected components of a flat 0/1 list: [(area, x0, y0, x1, y1, pixels)]."""
    seen = bytearray(len(bits))
    out = []
    for start, b in enumerate(bits):
        if not b or seen[start]:
            continue
        seen[start] = 1
        stack, pixels = [start], []
        while stack:
            i = stack.pop()
            pixels.append(i)
            x, y = i % w, i // w
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if ok and bits[j] and not seen[j]:
                    seen[j] = 1
                    stack.append(j)
        xs = [i % w for i in pixels]
        ys = [i // w for i in pixels]
        out.append((len(pixels), min(xs), min(ys), max(xs) + 1, max(ys) + 1, pixels))
    return out


def _clean(im, tile=None, max_parts=None):
    """Drop specks, slivers along the avatar edge, and the rim a tile leaves behind. Returns (mask, bbox)."""
    w, h = im.size
    small = im.reduce(4)
    sw, sh = small.size
    found = _components([1 if v > 40 else 0 for v in _pixels(small)], sw, sh)
    if not found:
        raise NoMark("empty")
    big = max(p[0] for p in found)
    parts = [p for p in found if p[0] >= max(4, .002 * big)]
    if max_parts and len(parts) > max_parts:
        raise NoMark(f"busy ({len(parts)} pieces)")
    rim = None
    if tile is not None:
        t = tile.reduce(4).point(lambda v: 255 if v > 128 else 0)
        rim = _pixels(ImageChops.subtract(t.filter(ImageFilter.MaxFilter(5)), t.filter(ImageFilter.MinFilter(9))))
    keep = []
    for area, x0, y0, x1, y1, pixels in parts:
        edge = x0 == 0 or y0 == 0 or x1 == sw or y1 == sh
        if edge and min(x1 - x0, y1 - y0) <= 3:
            continue
        if rim is not None and sum(1 for i in pixels if rim[i]) >= .7 * area:
            continue
        keep.append((x0, y0, x1, y1, pixels))
    if not keep:
        raise NoMark("empty")
    if len(keep) < len(found):
        flat = bytearray(sw * sh)
        for *_, pixels in keep:
            for i in pixels:
                flat[i] = 255
        gate = Image.frombytes("L", (sw, sh), bytes(flat)).resize((w, h), Image.NEAREST).filter(ImageFilter.MaxFilter(9))
        im = ImageChops.multiply(im, gate)
    x0 = min(k[0] for k in keep) * 4
    y0 = min(k[1] for k in keep) * 4
    x1 = max(k[2] for k in keep) * 4
    y1 = max(k[3] for k in keep) * 4
    region = (max(0, x0 - 4), max(0, y0 - 4), min(w, x1 + 4), min(h, y1 + 4))
    inner = im.crop(region).point(lambda v: 255 if v > 24 else 0).getbbox()
    if not inner:
        raise NoMark("empty")
    return im, (region[0] + inner[0], region[1] + inner[1], region[0] + inner[2], region[1] + inner[3])


def key(img, mode="auto", ramp_=None, crop=None, close=0):
    """Return (mask, coverage, mode_used). Raises NoMark when nothing usable comes out."""
    src = img.convert("RGBA")
    if src.size != (SIZE, SIZE):
        src = src.resize((SIZE, SIZE), Image.LANCZOS)
    if crop:
        x0, y0, x1, y1 = crop
        src = src.crop((round(x0 * SIZE), round(y0 * SIZE), round(x1 * SIZE), round(y1 * SIZE)))
    w, h = src.size
    px = _pixels(src)
    alpha = [p[3] for p in px]
    rgb = [((p[0] * p[3] + 255 * (255 - p[3])) // 255, (p[1] * p[3] + 255 * (255 - p[3])) // 255,
            (p[2] * p[3] + 255 * (255 - p[3])) // 255) for p in px]

    tile, auto = None, mode == "auto"
    if auto:
        m, mode, tile = choose(rgb, alpha, w, h)
        if mode != "alpha" and flatness(rgb, alpha) < MIN_FLAT:
            raise NoMark("a photo, not a logo")
        if noise(m) > MAX_NOISE:
            raise NoMark(f"too soft to key ({noise(m):.2f})")
    else:
        a0, a1 = ramp_ or RAMPS.get(mode, (0, 1))
        if mode == "diff":
            opaque = sorted((rgb[i] for i in _border(w, h) if alpha[i] >= 128), key=sum) or [(255, 255, 255)]
            bg = opaque[len(opaque) // 2]
            m = [ramp(_dist(c, bg), a0, a1) * a / 255 for c, a in zip(rgb, alpha)]
        elif mode == "dark":
            m = [ramp(255 - (c[0] * .3 + c[1] * .59 + c[2] * .11), a0, a1) * a / 255 for c, a in zip(rgb, alpha)]
        elif mode == "white":
            m = [ramp(min(c), a0, a1) * a / 255 for c, a in zip(rgb, alpha)]
        elif mode == "solid":
            m = [a / 255 * (1 - ramp(min(c), 170, 235)) for c, a in zip(rgb, alpha)]
        elif mode == "inner":
            m0 = _base(rgb, alpha, w, h)[0]
            got = _inner(rgb, m0, w, h, (a0, a1))
            m, tile = got if got else (m0, None)
        elif mode == "alpha":
            m = [a / 255 for a in alpha]
        else:
            raise ValueError(f"unknown mode {mode}")

    # one ink, no greys: threshold the mask here, the downscale to display size brings the soft edge back
    im = _to_l([1.0 if v >= .5 else 0.0 for v in m], w, h)
    if close:
        im = im.filter(ImageFilter.MaxFilter(close)).filter(ImageFilter.MinFilter(close))
    im, box = _clean(im, tile, MAX_PARTS)
    im = im.crop(box)
    if im.size[0] < 8 or im.size[1] < 8:
        raise NoMark("too small")
    if auto and _fine(im) > MAX_FINE:
        raise NoMark("too fine to read at strip size")
    hist = im.histogram()
    cov = sum(i * n for i, n in enumerate(hist)) / (255 * im.size[0] * im.size[1])
    return im, cov, mode
