import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from brand_ticker import render
from brand_ticker.marks import Mark

NS = {"s": "http://www.w3.org/2000/svg"}


def vec(w=24, h=24, cov=.5):
    return Mark("x", w, h, cov, path="M0 0h24v24H0z")


def ras(w=100, h=100):
    m = Image.new("L", (w, h), 255)
    return Mark("y", w, h, 1.0, mask=m)


@pytest.mark.parametrize("num", ["3,268", "12,345", "999", "1,000,000", "1,111"])
def test_number_runs_edge_to_edge(num):
    L = render.number_layout(num)
    assert L["ink"] == pytest.approx(render.W, abs=.01)
    assert L["x"] < 0                                  # the first side bearing hangs off the left edge
    assert L["advance"] > L["ink"] * .95


@pytest.mark.parametrize("num", ["7", "42"])
def test_short_numbers_stop_growing(num):
    L = render.number_layout(num)
    assert L["cap"] == pytest.approx(render.MAX_CAP)
    assert L["ink"] < render.W


def test_more_digits_means_smaller_type():
    sizes = [render.number_layout(n)["size"] for n in ["999", "9,999", "99,999", "999,999"]]
    assert sizes == sorted(sizes, reverse=True)


def test_marks_weigh_the_same():
    square = render.mark_box(vec(24, 24))
    wide = render.mark_box(vec(48, 12))
    assert square[0] * square[1] == pytest.approx(wide[0] * wide[1], rel=.01)


def test_tall_marks_are_clamped():
    mw, mh = render.mark_box(vec(4, 24))
    assert mh == pytest.approx(render.MARK * 1.08)


def test_very_wide_marks_are_clamped():
    mw, mh = render.mark_box(vec(240, 10))
    assert mw == pytest.approx(render.MARK * 2.6)


def test_dense_marks_are_a_touch_smaller():
    solid = render.mark_box(vec(cov=.95))
    thin = render.mark_box(vec(cov=.2))
    assert solid[1] < thin[1]


def parse(svg):
    return ET.fromstring(svg)


def test_svg_is_valid_and_animated():
    root = parse(render.svg(3268, [vec(), ras(), vec(48, 12)], "#191A1C"))
    assert root.get("width") == "840"
    style = root.find("s:style", NS).text
    assert "prefers-reduced-motion:reduce" in style and "animation:none" in style
    assert "@keyframes s" in style
    text = root.find("s:text", NS)
    assert text.text == "3,268"
    assert text.get("lengthAdjust") == "spacing" and float(text.get("textLength")) > 800
    assert root.find("s:title", NS).text == "3,268 contributions in the last year"
    assert len(root.findall(".//s:image", NS)) == 1    # the raster mark, once, as a def
    assert root.find("s:rect", NS) is None             # see through by default


def test_svg_ground_when_asked():
    root = parse(render.svg(10, [vec()], "#FFFFFF", bg="#0D1117"))
    assert root.find("s:rect", NS).get("fill") == "#0D1117"


def test_no_marks_no_strip():
    svg = render.svg(512, [], "#191A1C")
    root = parse(svg)
    assert "@keyframes" not in svg and root.find(".//s:use", NS) is None
    L = render.number_layout("512")
    assert int(root.get("height")) == round(round(render.TOP + L["cap"]) + L["desc"] + render.BOTTOM)


def test_short_run_spreads_over_the_width():
    svg = render.svg(100, [vec(), vec()], "#000000")
    period = float(svg.split("translateX(-")[1].split("px")[0])
    assert period == pytest.approx(render.W, abs=.5)


def test_long_run_keeps_its_gap():
    svg = render.svg(100, [vec()] * 20, "#000000")
    period = float(svg.split("translateX(-")[1].split("px")[0])
    mw, _ = render.mark_box(vec())
    assert period == pytest.approx(20 * (mw + render.MARK_GAP), abs=.5)


def test_strip_tiles_past_both_edges():
    root = parse(render.svg(100, [vec()] * 3, "#000000"))
    copies = root.findall(".//s:g[@class='s']/s:g", NS)
    assert len(copies) >= 3


@pytest.mark.parametrize("given,want", [("#abc", "#AABBCC"), ("191a1c", "#191A1C"), ("#F0F3F6", "#F0F3F6")])
def test_colours(given, want):
    assert render.color(given) == want


def test_bad_colour():
    with pytest.raises(ValueError):
        render.color("red")
    assert render.color("none", allow_none=True) == "none"
