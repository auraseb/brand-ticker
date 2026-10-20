"""python -m brand_ticker --user <login> --out ticker"""
import argparse, os, pathlib, sys
from concurrent.futures import ThreadPoolExecutor

from . import fetch, marks as M, render


def split(v):
    return [s.strip() for s in (v or "").replace("\n", ",").split(",") if s.strip()]


def args(argv=None):
    p = argparse.ArgumentParser(prog="brand_ticker", description=__doc__)
    p.add_argument("--user", required=True)
    p.add_argument("--mode", default="prs_and_issues", choices=sorted(fetch.MODES))
    p.add_argument("--min-stars", type=int, default=100)
    p.add_argument("--exclude", default="", help="org logins to leave out, comma separated")
    p.add_argument("--first", default="", help="org logins to lead the strip, comma separated")
    p.add_argument("--max-logos", type=int, default=30)
    p.add_argument("--light-ink", default=render.DEFAULT_THEMES["light"]["ink"])
    p.add_argument("--dark-ink", default=render.DEFAULT_THEMES["dark"]["ink"])
    p.add_argument("--light-bg", default="none")
    p.add_argument("--dark-bg", default="none")
    p.add_argument("--out", default="ticker")
    p.add_argument("--badge-merged", default="true", help="mark logos of orgs where a PR was merged")
    p.add_argument("--layout", default="count", choices=["count", "strip", "marquee", "wall"], help="count: the number over one strip; strip: the strip alone; marquee: two big counter scrolling rows; wall: a still grid")
    p.add_argument("--token", default=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    return p.parse_args(argv)


def gather(found, limit, workers=8):
    """Marks for the ranked orgs, skipping any whose avatar holds no usable mark, up to limit."""
    def one(e):
        v = M.vector(e["login"])
        if v and not M.OVERRIDES.get(e["login"].lower(), {}).get("skip"):
            return v
        try:
            return M.resolve(e["login"], fetch.avatar(e["avatar"], e["login"]), vectors=False)
        except Exception as err:  # one bad avatar never sinks the run
            print(f"  skip {e['login']}: {err}", file=sys.stderr)
            return None

    out = []
    with ThreadPoolExecutor(workers) as pool:
        for i in range(0, len(found), limit):
            for m in pool.map(one, found[i:i + limit]):
                if m and len(out) < limit:
                    out.append(m)
            if len(out) >= limit:
                break
    return out


def main(argv=None):
    a = args(argv)
    themes = {"light": (render.color(a.light_ink), render.color(a.light_bg, True)),
              "dark": (render.color(a.dark_ink), render.color(a.dark_bg, True))}
    count = fetch.contributions(a.user, a.token)
    found = fetch.orgs(a.user, a.mode, a.token, a.min_stars, split(a.exclude))
    merged = set()
    if a.badge_merged.lower() == "true":
        merged = set(found) if a.mode == "merged_prs" else set(fetch.orgs(a.user, "merged_prs", a.token, a.min_stars, split(a.exclude)))
    # orgs that merged your code lead the strip (after any you pin), so their mark is always in view
    first = split(a.first) + sorted(o for o in merged if o not in {f.lower() for f in split(a.first)})
    ranked = fetch.rank(found, a.token, first)
    marks = gather(ranked, max(0, a.max_logos)) if a.max_logos > 0 else []

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, (ink, bg) in themes.items():
        if a.layout == "strip":
            doc = render.marquee(marks, ink, bg, merged=merged, side=64, rows=1)
        elif a.layout == "marquee":
            doc = render.marquee(marks, ink, bg, merged=merged)
        elif a.layout == "wall":
            doc = render.wall(marks, ink, bg, merged=merged)
        else:
            doc = render.svg(count, marks, ink, bg, merged=merged)
        (out / f"{name}.svg").write_text(doc)

    logins = [m.org for m in marks]
    print(f"{count:,} contributions, {len(marks)} marks: {', '.join(logins) or 'none'}")
    for m in marks:
        print(f"  {m.org:<28} {m.source}{'  merged' if m.org.lower() in merged else ''}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"contributions={count}\norgs={','.join(logins)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
