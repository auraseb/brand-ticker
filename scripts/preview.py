#!/usr/bin/env python3
"""PNG previews of <dir>/light.svg and <dir>/dark.svg on GitHub's own grounds, through a headless Chromium.

  python3 scripts/preview.py ticker [--at 6] [--width 840]

--at seeks the scroll to that many seconds in, so a still shows the strip mid flight.
Uses CHROME, else the Playwright headless shell. Never the full browser app.
"""
import argparse, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from bundle_icons import chrome  # noqa: E402

GROUNDS = {"light": "#ffffff", "dark": "#0d1117"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dir")
    p.add_argument("--at", type=float, default=0.0)
    p.add_argument("--width", type=int, default=840)
    a = p.parse_args()
    d = pathlib.Path(a.dir).resolve()
    for theme, ground in GROUNDS.items():
        src = (d / f"{theme}.svg").read_text()
        h = int(re.search(r'<svg[^>]* height="(\d+)"', src).group(1))
        scale = a.width / 840
        page = d / f"_{theme}.html"
        page.write_text(f'<html><body style="margin:0;background:{ground}">'
                        f'<div style="padding:24px">{src}</div>'
                        f"<style>.s{{animation-delay:-{a.at}s!important;animation-play-state:paused!important}}</style>"
                        "</body></html>")
        out = d / f"{theme}.png"
        subprocess.run([chrome(), "--headless", f"--screenshot={out}", f"--window-size={a.width + 48},{round(h * scale) + 48}",
                        "--hide-scrollbars", "--force-device-scale-factor=2", f"file://{page}"],
                       capture_output=True, check=True)
        page.unlink()
        print(out)


if __name__ == "__main__":
    main()
