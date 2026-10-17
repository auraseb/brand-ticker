import pathlib
import random

import pytest
from PIL import Image, ImageDraw

from brand_ticker import marks
from brand_ticker.keying import NoMark, _pixels, key

AVATARS = pathlib.Path(__file__).parent / "avatars"


def avatar(name):
    return Image.open(AVATARS / f"{name}.png")


def ink_at(mask, fx, fy):
    """Mask value at a fraction of its own box."""
    w, h = mask.size
    return mask.getpixel((min(w - 1, int(fx * w)), min(h - 1, int(fy * h))))


def test_vercel_triangle_on_black():
    m, cov, mode = key(avatar("vercel"))
    assert mode == "diff"
    w, h = m.size
    assert 1.0 < w / h < 1.3          # an equilateral triangle, wider than tall
    assert .4 < cov < .6              # half its box
    assert ink_at(m, .5, .9) > 200    # base is inked
    assert ink_at(m, .05, .05) < 30   # corners are not


def test_openai_dark_mark_on_white():
    m, cov, mode = key(avatar("openai"))
    assert mode == "diff"
    assert .9 < m.size[0] / m.size[1] < 1.1
    assert .25 < cov < .55


def test_badge_gives_the_mark_not_the_badge():
    # a white mark on a one colour tile: the tile must go
    for name in ("swiftlang", "preactjs"):
        m, cov, mode = key(avatar(name))
        assert mode == "inner", name
        assert cov < .6, name
        assert m.size[0] < 460 * .9 and m.size[1] < 460 * .9, name


def test_badge_rim_leaves_no_slivers():
    m, _, _ = key(avatar("preactjs"))
    w, h = m.size
    # the atom is about as wide as tall; slivers of the hexagon would stretch it sideways
    assert .9 < w / h < 1.5
    edge = [m.getpixel((w - 1, y)) for y in range(h)]
    assert max(edge) > 0 and sum(v > 128 for v in edge) < h * .5


def test_transparent_ground_uses_alpha():
    m, cov, mode = key(avatar("planetlabs"))
    assert mode == "alpha"
    assert ink_at(m, .5, .5) < 255    # a ring with a letter, not a disc


def test_tesla_override_keys_white_t():
    o = marks.OVERRIDES["teslamotors"]
    m, cov, mode = key(avatar("teslamotors"), mode=o["mode"])
    assert mode == "white"
    assert ink_at(m, .5, .6) > 200    # the stem of the T
    assert ink_at(m, .1, .9) < 30


def test_tesla_auto_also_finds_the_t():
    m, cov, mode = key(avatar("teslamotors"))
    assert mode in ("inner", "white")
    assert cov < .45


def test_mask_is_one_ink():
    for name in ("vercel", "openai", "swiftlang"):
        m, _, _ = key(avatar(name))
        assert set(_pixels(m)) <= {0, 255}, name


def test_four_colour_squares_are_not_a_tile():
    im = Image.new("RGB", (200, 200), "white")
    d = ImageDraw.Draw(im)
    for (x, y), c in zip([(10, 10), (102, 10), (10, 102), (102, 102)], ["#f25022", "#7fba00", "#00a4ef", "#ffb900"]):
        d.rectangle((x, y, x + 88, y + 88), fill=c)
    m, cov, mode = key(im)
    assert mode == "diff"
    assert cov > .85                  # all four squares, solid


@pytest.mark.parametrize("inset,want", [(0, "diff"), (16, "inner")])
def test_white_glyph_in_rounded_tile(inset, want):
    # full bleed tile: its colour is the ground. inset tile on a clear ground: a badge to look inside
    im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((inset, inset, 199 - inset, 199 - inset), radius=40, fill=(220, 40, 40, 255))
    d.ellipse((70, 70, 130, 130), fill=(255, 255, 255, 255))
    m, cov, mode = key(im)
    assert mode == want
    assert .85 < m.size[0] / m.size[1] < 1.15
    assert m.size[0] < 200            # the dot, at 460 scale about 140 px, not the tile


def test_photo_is_refused():
    rnd = random.Random(7)
    im = Image.new("RGB", (120, 120))
    im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(120 * 120)])
    with pytest.raises(NoMark):
        key(im)


def test_blank_avatar_is_refused():
    with pytest.raises(NoMark):
        key(Image.new("RGB", (100, 100), "white"))


def test_resolve_prefers_vectors_and_keys_the_rest():
    v = marks.resolve("vercel", None)
    assert v.path and v.source == "simple-icons:vercel"
    r = marks.resolve("some-org", (AVATARS / "openai.png").read_bytes())
    assert r.mask is not None and r.source.startswith("avatar:")
    assert marks.resolve("some-org", None) is None


def test_slug_table_and_name_match():
    assert marks.slug_for("teslamotors") == "tesla"
    assert marks.slug_for("Facebook") == "meta"
    assert marks.slug_for("stripe") == "stripe"
    assert marks.slug_for("nobody-here") is None
