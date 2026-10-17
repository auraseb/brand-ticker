"""Turn an org into one mark: a Simple Icons vector when the brand is bundled, else its keyed avatar."""
import base64, io, json, pathlib, re
from dataclasses import dataclass

from PIL import Image

from .keying import NoMark, key

DATA = pathlib.Path(__file__).resolve().parent / "data"
ICONS = json.loads((DATA / "simple-icons.json").read_text())
OVERRIDES = {k: v for k, v in json.loads((DATA / "overrides.json").read_text()).items() if not k.startswith("_")}


@dataclass
class Mark:
    org: str
    w: float          # ink box width and height in source units
    h: float
    cov: float        # share of the ink box that is inked, 0..1
    path: str = ""    # vector: Simple Icons path in a 24 unit box
    x: float = 0.0
    y: float = 0.0
    mask: Image.Image = None  # raster: alpha mask cropped to the ink
    scale: float = 1.0
    source: str = ""


def norm(login):
    return re.sub(r"[^a-z0-9]", "", login.lower())


def slug_for(login):
    """Simple Icons slug for an org login, from the curated table, else an exact name match."""
    low = login.lower()
    if low in ICONS["orgs"]:
        return ICONS["orgs"][low]
    n = norm(login)
    return n if n in ICONS["icons"] else None


def vector(login):
    slug = slug_for(login)
    if not slug:
        return None
    i = ICONS["icons"][slug]
    x, y, w, h = i["bbox"]
    return Mark(login, w, h, i["cov"], path=i["path"], x=x, y=y, source=f"simple-icons:{slug}")


def raster(login, avatar_bytes):
    """Key the avatar. Returns None when it holds no usable mark (a photo, a gradient)."""
    o = OVERRIDES.get(login.lower(), {})
    if o.get("skip"):
        return None
    img = Image.open(io.BytesIO(avatar_bytes))
    try:
        m, cov, mode = key(img, mode=o.get("mode", "auto"), ramp_=o.get("ramp"), crop=o.get("crop"),
                           close=o.get("close", 0))
    except NoMark:
        return None
    return Mark(login, m.size[0], m.size[1], cov, mask=m, scale=o.get("scale", 1.0), source=f"avatar:{mode}")


def resolve(login, avatar_bytes=None, vectors=True):
    """The mark for one org, or None."""
    if OVERRIDES.get(login.lower(), {}).get("skip"):
        return None
    if vectors:
        v = vector(login)
        if v:
            return v
    return raster(login, avatar_bytes) if avatar_bytes else None


def png_uri(mask, ink, dw, dh, density=2):
    """The mark in one ink, at density x its display size, on a transparent ground."""
    m = mask.resize((max(1, round(dw * density)), max(1, round(dh * density))), Image.LANCZOS)
    rgb = tuple(int(ink.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    im = Image.new("RGBA", m.size, rgb + (0,))
    im.putalpha(m)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
