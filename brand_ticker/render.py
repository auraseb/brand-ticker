"""Layout and SVG: the count edge to edge, one slow line of marks below it.

Pure SVG with one CSS animation, so it survives GitHub's image proxy. No fonts are embedded:
the number is set in the system stack and textLength pins it to the full width on any font.
"""
import json, math, pathlib, re
from html import escape

from .marks import png_uri

METRICS = {k: v for k, v in json.loads((pathlib.Path(__file__).resolve().parent / "data" / "metrics.json").read_text()).items()
           if not k.startswith("_")}

W = 840
SANS = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', Inter, 'Segoe UI', Helvetica, Arial, sans-serif"
WEIGHT, TRACK = 800, -0.03
MAX_CAP = 0.4 * W  # one or two digit counts stop growing here and sit flush left
TOP = 6            # room above the digit overshoot
GAP = 84           # baseline to the top of the mark row
MARK = 58          # a square mark is MARK x MARK; other shapes keep the same visual mass
MARK_GAP = 68      # equal white space between marks
BOTTOM = 8
SPEED = 24         # px per second
FADE = 96          # the strip fades out over this many px at both ends
BADGE = 18         # the merged mark (GitHub's git merge glyph) beside a logo whose PR landed
# Octicons git-merge-24, MIT licensed, https://github.com/primer/octicons
MERGE_PATH = ("M15 13.25a3.25 3.25 0 1 1 6.5 0 3.25 3.25 0 0 1-6.5 0Zm-12.5 6a3.25 3.25 0 1 1 6.5 0 3.25 3.25 0 0 1-6.5 0Zm0-14.5"
              "a3.25 3.25 0 1 1 6.5 0 3.25 3.25 0 0 1-6.5 0ZM5.75 6.5a1.75 1.75 0 1 0-.001-3.501A1.75 1.75 0 0 0 5.75 6.5Zm0 14.5"
              "a1.75 1.75 0 1 0-.001-3.501A1.75 1.75 0 0 0 5.75 21Zm12.5-6a1.75 1.75 0 1 0-.001-3.501A1.75 1.75 0 0 0 18.25 15Z"
              "M6.5 7.25c0 2.9 2.35 5.25 5.25 5.25h4.5V14h-4.5A6.75 6.75 0 0 1 5 7.25Z"
              "M5.75 16.75A.75.75 0 0 1 5 16V8a.75.75 0 0 1 1.5 0v8a.75.75 0 0 1-.75.75Z")

DEFAULT_THEMES = {
    "light": {"ink": "#191A1C", "bg": "none"},
    "dark": {"ink": "#F0F3F6", "bg": "none"},
}


def color(value, allow_none=False):
    """#RGB or #RRGGBB, normalised to #RRGGBB. 'none' or empty means no ground."""
    v = (value or "").strip()
    if allow_none and v.lower() in ("", "none", "transparent"):
        return "none"
    if not v.startswith("#"):
        v = "#" + v
    if re.fullmatch(r"#[0-9a-fA-F]{3}", v):
        v = "#" + "".join(c * 2 for c in v[1:])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
        raise ValueError(f"not a hex colour: {value!r}")
    return v.upper()


def number_layout(num, width=W, metrics=METRICS, track=TRACK, max_cap=MAX_CAP):
    """Font size that runs the ink exactly edge to edge (capped for very short numbers).

    Returns size (px), x (text origin so the first glyph's ink starts at 0), advance (textLength),
    ink (ink width in px), cap (tallest digit above the baseline) and desc (deepest ink below it).
    """
    pen, first, right = 0.0, None, 0.0
    for ch in num:
        adv, x0, x1, _, _ = metrics[ch]
        if first is None:
            first = x0
        right = pen + x1
        pen += adv + track
    ink_em = right - first
    size = width / ink_em
    cap_em = max(metrics[c][4] for c in num)
    if cap_em * size > max_cap:
        size = max_cap / cap_em
    desc_em = max(-metrics[c][3] for c in num)
    return {"size": size, "x": -first * size, "advance": pen * size, "ink": ink_em * size,
            "cap": cap_em * size, "desc": desc_em * size}


def mark_box(mark, side=MARK):
    """Display size: equal visual mass for every mark, dense marks a touch smaller, then clamped."""
    a = mark.w / mark.h
    mh = side / math.sqrt(a) * (0.42 / max(mark.cov, .12)) ** .22 * mark.scale
    mh = min(mh, side * 1.08)
    mw = mh * a
    if mw > side * 2.6:
        mw, mh = side * 2.6, side * 2.6 / a
    return mw, mh


def _mark_def(i, mark, ink, mw, mh):
    if mark.path:
        s = mh / mark.h
        return (f'<g id="m{i}"><path fill="{ink}" transform="scale({s:.4f}) translate({-mark.x:.3f} {-mark.y:.3f})" '
                f'd="{mark.path}"/></g>')
    return f'<g id="m{i}"><image href="{png_uri(mark.mask, ink, mw, mh)}" width="{mw:.2f}" height="{mh:.2f}"/></g>'


def svg(count, marks, ink, bg="none", width=W, label="contributions in the last year", merged=()):
    """One theme of the ticker as an SVG string."""
    num = f"{count:,}"
    L = number_layout(num, width)
    base = round(TOP + L["cap"])
    boxes = [mark_box(m) for m in marks]

    if marks:
        tallest = max(mh for _, mh in boxes)
        row_mid = base + GAP + MARK / 2
        H = round(row_mid + max(MARK, tallest) / 2 + BOTTOM)
    else:
        H = round(base + L["desc"] + BOTTOM)

    css = (f".n{{font-family:{SANS};font-size:{L['size']:.2f}px;font-weight:{WEIGHT};letter-spacing:{TRACK}em;"
           "font-variant-numeric:proportional-nums}")
    defs, body = [], []
    if bg != "none":
        body.append(f'<rect width="{width}" height="{H}" fill="{bg}"/>')

    if marks:
        # a short run spreads out to fill the width, so no mark shows twice at once
        gap = max(MARK_GAP, (width - sum(mw for mw, _ in boxes)) / len(marks))
        merged = {o.lower() for o in merged}
        if merged & {m.org.lower() for m in marks}:
            s = BADGE / 24
            defs.append(f'<g id="merged"><path fill="{ink}" transform="scale({s:.4f})" d="{MERGE_PATH}"/></g>')
        items, x = [], 0.0
        for i, (m, (mw, mh)) in enumerate(zip(marks, boxes)):
            defs.append(_mark_def(i, m, ink, mw, mh))
            items.append(f'<use href="#m{i}" x="{x:.2f}" y="{row_mid - mh / 2:.2f}"/>')
            if m.org.lower() in merged:  # sits just off the logo's top right corner, no ground behind it
                items.append(f'<use href="#merged" x="{x + mw + 4:.2f}" y="{row_mid - mh / 2 - BADGE * 0.55:.2f}"/>')
            x += mw + gap
        run, period = "".join(items), x
        copies = math.ceil(width / period) + 1
        strip = "".join(f'<g transform="translate({k * period:.2f} 0)">{run}</g>' for k in range(-1, copies))
        css += (f"@keyframes s{{from{{transform:translateX(0)}}to{{transform:translateX(-{period:.2f}px)}}}}"
                f".s{{animation:s {period / SPEED:.1f}s linear infinite}}"
                "@media (prefers-reduced-motion:reduce){.s{animation:none}}")
        top = base + 8
        defs.append(f'<linearGradient id="fade" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{width}" y2="0">'
                    f'<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                    f'<stop offset="{FADE / width:.4f}" stop-color="#fff"/>'
                    f'<stop offset="{1 - FADE / width:.4f}" stop-color="#fff"/>'
                    f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
                    f'<mask id="edge" maskUnits="userSpaceOnUse" x="0" y="{top}" width="{width}" height="{H - top}">'
                    f'<rect x="0" y="{top}" width="{width}" height="{H - top}" fill="url(#fade)"/></mask>')
        lead = FADE + 8  # the opening frame, and the reduced motion frame, start clear of the fade
        body.append(f'<g mask="url(#edge)"><g transform="translate({lead} 0)"><g class="s">{strip}</g></g></g>')

    body.append(f'<text class="n" x="{L["x"]:.2f}" y="{base}" fill="{ink}" textLength="{L["advance"]:.2f}" '
                f'lengthAdjust="spacing">{num}</text>')
    title = escape(f"{num} {label}")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{H}" viewBox="0 0 {width} {H}" '
            f'role="img" aria-label="{title}">\n<title>{title}</title>\n<style>{css}</style>\n'
            f'<defs>{"".join(defs)}</defs>\n' + "\n".join(body) + "\n</svg>\n")


def _badge_def(ink, size):
    s = size / 24
    return f'<g id="merged"><path fill="{ink}" transform="scale({s:.4f})" d="{MERGE_PATH}"/></g>'


def _strip(marks, boxes, ink, merged, width, mid, side, gap_min, badge, prefix):
    """One looping row of marks centred on y=mid; returns (defs, group, period)."""
    gap = max(gap_min, (width - sum(mw for mw, _ in boxes)) / len(marks))
    defs, items, x = [], [], 0.0
    for i, (m, (mw, mh)) in enumerate(zip(marks, boxes)):
        defs.append(_mark_def(f"{prefix}{i}", m, ink, mw, mh))
        items.append(f'<use href="#m{prefix}{i}" x="{x:.2f}" y="{mid - mh / 2:.2f}"/>')
        if m.org.lower() in merged:
            items.append(f'<use href="#merged" x="{x + mw + 4:.2f}" y="{mid - mh / 2 - badge * 0.55:.2f}"/>')
        x += mw + gap
    run, period = "".join(items), x
    copies = math.ceil(width / period) + 1
    strip = "".join(f'<g transform="translate({k * period:.2f} 0)">{run}</g>' for k in range(-1, copies))
    return defs, strip, period


def marquee(marks, ink, bg="none", width=W, merged=(), side=84, rows=2, label="companies I ship fixes to"):
    """No number: the marks are the headline, in counter scrolling rows (merged orgs lead)."""
    merged = {o.lower() for o in merged}
    badge = round(side * 0.3)
    row_h = side * 1.55
    H = round(row_h * rows + 8)
    lanes = [marks[i::rows] for i in range(rows)]
    defs, body, css = [], [], []
    if merged & {m.org.lower() for m in marks}:
        defs.append(_badge_def(ink, badge))
    if bg != "none":
        body.append(f'<rect width="{width}" height="{H}" fill="{bg}"/>')
    defs.append(f'<linearGradient id="fade" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{width}" y2="0">'
                f'<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="{FADE / width:.4f}" stop-color="#fff"/>'
                f'<stop offset="{1 - FADE / width:.4f}" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
                f'</linearGradient><mask id="edge" maskUnits="userSpaceOnUse" x="0" y="0" width="{width}" height="{H}">'
                f'<rect width="{width}" height="{H}" fill="url(#fade)"/></mask>')
    groups = []
    for r, lane in enumerate(lanes):
        if not lane:
            continue
        boxes = [mark_box(m, side) for m in lane]
        mid = row_h * r + row_h / 2 + 4
        d, strip, period = _strip(lane, boxes, ink, merged, width, mid, side, side * 0.9, badge, f"r{r}")
        defs += d
        dur = period / SPEED
        css.append(f"@keyframes k{r}{{from{{transform:translateX({0 if r % 2 == 0 else -period:.2f}px)}}"
                   f"to{{transform:translateX({-period if r % 2 == 0 else 0:.2f}px)}}}}"
                   f".k{r}{{animation:k{r} {dur:.1f}s linear infinite}}")
        groups.append(f'<g transform="translate({FADE + 8} 0)"><g class="k{r}">{strip}</g></g>')
    css.append("@media (prefers-reduced-motion:reduce){" + "".join(f".k{r}{{animation:none}}" for r in range(rows)) + "}")
    body.append(f'<g mask="url(#edge)">{"".join(groups)}</g>')
    title = escape(label)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{H}" viewBox="0 0 {width} {H}" '
            f'role="img" aria-label="{title}">\n<title>{title}</title>\n<style>{"".join(css)}</style>\n'
            f'<defs>{"".join(defs)}</defs>\n' + "\n".join(body) + "\n</svg>\n")


def wall(marks, ink, bg="none", width=W, merged=(), cols=7, label="companies I ship fixes to"):
    """No number: a still grid of every mark, merged orgs first with the merge glyph."""
    merged = {o.lower() for o in merged}
    cell = width / cols
    side = cell * 0.5
    badge = round(side * 0.32)
    rows = math.ceil(len(marks) / cols)
    H = round(cell * 0.8 * rows)
    defs, body = [], []
    if merged & {m.org.lower() for m in marks}:
        defs.append(_badge_def(ink, badge))
    if bg != "none":
        body.append(f'<rect width="{width}" height="{H}" fill="{bg}"/>')
    for i, m in enumerate(marks):
        mw, mh = mark_box(m, side)
        cx, cy = (i % cols + 0.5) * cell, (i // cols + 0.5) * cell * 0.8
        defs.append(_mark_def(f"w{i}", m, ink, mw, mh))
        body.append(f'<use href="#mw{i}" x="{cx - mw / 2:.2f}" y="{cy - mh / 2:.2f}"/>')
        if m.org.lower() in merged:
            body.append(f'<use href="#merged" x="{cx + mw / 2 + 4:.2f}" y="{cy - mh / 2 - badge * 0.55:.2f}"/>')
    title = escape(label)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{H}" viewBox="0 0 {width} {H}" '
            f'role="img" aria-label="{title}">\n<title>{title}</title>\n'
            f'<defs>{"".join(defs)}</defs>\n' + "\n".join(body) + "\n</svg>\n")
