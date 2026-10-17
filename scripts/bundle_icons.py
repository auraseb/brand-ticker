#!/usr/bin/env python3
"""Rebuild brand_ticker/data/simple-icons.json from a Simple Icons release (CC0).

  npm pack simple-icons && tar xzf simple-icons-*.tgz
  python3 scripts/bundle_icons.py package/

Measures each path's ink box and coverage with a headless Chromium (CHROME env, or the
Playwright headless shell), so the action itself never needs a browser.
"""
import json, os, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "brand_ticker" / "data" / "simple-icons.json"

# GitHub org login (lowercase) -> Simple Icons slug. Left out on purpose: marks that Simple Icons draws
# inside a filled tile (swift, maplibre, datadog); their avatars key out cleaner.
ORGS = {
    "apple": "apple", "google": "google", "facebook": "meta", "github": "github", "vercel": "vercel",
    "cloudflare": "cloudflare", "nasa": "nasa", "mozilla": "mozilla", "anthropics": "anthropic",
    "teslamotors": "tesla", "nytimes": "newyorktimes", "figma": "figma", "tailwindlabs": "tailwindcss",
    "oven-sh": "bun", "internetarchive": "internetarchive", "docker": "docker", "kubernetes": "kubernetes",
    "golang": "go", "rust-lang": "rust", "python": "python", "nodejs": "nodedotjs", "denoland": "deno",
    "vuejs": "vuedotjs", "angular": "angular", "sveltejs": "svelte", "vitejs": "vite", "withastro": "astro",
    "remix-run": "remix", "prisma": "prisma", "supabase": "supabase", "shopify": "shopify", "stripe": "stripe",
    "netflix": "netflix", "airbnb": "airbnb", "spotify": "spotify", "hashicorp": "hashicorp",
    "grafana": "grafana", "elastic": "elastic", "mongodb": "mongodb", "redis": "redis", "postgres": "postgresql",
    "huggingface": "huggingface", "pytorch": "pytorch", "tensorflow": "tensorflow", "jupyter": "jupyter",
    "numpy": "numpy", "pandas-dev": "pandas", "astral-sh": "astral", "nvidia": "nvidia",
    "posthog": "posthog", "getsentry": "sentry", "gitlabhq": "gitlab", "jetbrains": "jetbrains",
    "netlify": "netlify", "firebase": "firebase", "vitest-dev": "vitest", "dotnet": "dotnet",
    "flutter": "flutter", "apache": "apache", "eslint": "eslint", "prettier": "prettier",
    "webpack": "webpack", "expo": "expo", "reactjs": "react", "nuxt": "nuxt", "laravel": "laravel",
    "rails": "rubyonrails", "home-assistant": "homeassistant", "godotengine": "godotengine", "ollama": "ollama",
    "langchain-ai": "langchain", "discord": "discord", "raycast": "raycast",
    "duckdb": "duckdb", "wordpress": "wordpress",
}

PAGE = """<html><body><svg id=s width=0 height=0></svg><pre id=o></pre><script>
const P = %s, out = {}, svg = document.getElementById('s'), N = 480;
const c = document.createElement('canvas'); c.width = c.height = N; const g = c.getContext('2d');
for (const [slug, d] of Object.entries(P)) {
  const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('d', d); svg.appendChild(p);
  const b = p.getBBox();
  g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, N, N); g.setTransform(N / 24, 0, 0, N / 24, 0, 0); g.fill(new Path2D(d));
  const px = g.getImageData(0, 0, N, N).data; let ink = 0;
  for (let i = 3; i < px.length; i += 4) ink += px[i];
  const area = (b.width * N / 24) * (b.height * N / 24) * 255;
  out[slug] = {bbox: [b.x, b.y, b.width, b.height].map(v => +v.toFixed(3)), cov: +(ink / area).toFixed(3)};
}
document.getElementById('o').textContent = JSON.stringify(out);
</script></body></html>"""


def chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    hits = sorted(pathlib.Path.home().glob("Library/Caches/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"))
    hits += sorted(pathlib.Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"))
    if not hits:
        sys.exit("set CHROME to a headless Chromium")
    return str(hits[-1])


def main(pkg):
    pkg = pathlib.Path(pkg)
    meta = {i["slug"]: i for i in json.loads((pkg / "data" / "simple-icons.json").read_text())}
    version = json.loads((pkg / "package.json").read_text())["version"]
    paths = {}
    for slug in sorted(set(ORGS.values())):
        svg = (pkg / "icons" / f"{slug}.svg").read_text()
        paths[slug] = re.search(r'<path d="([^"]+)"', svg).group(1)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(PAGE % json.dumps(paths))
    dom = subprocess.run([chrome(), "--headless", "--dump-dom", "--virtual-time-budget=5000", f"file://{f.name}"],
                         capture_output=True, text=True, check=True).stdout
    os.unlink(f.name)
    measured = json.loads(re.search(r'<pre id="o">(.*?)</pre>', dom, re.S).group(1))
    icons = {s: {"title": meta[s]["title"], "path": paths[s], **measured[s]} for s in sorted(paths)}
    OUT.write_text(json.dumps({"source": f"simple-icons {version}", "license": "CC0-1.0",
                               "orgs": dict(sorted(ORGS.items())), "icons": icons}, indent=1) + "\n")
    print(f"{len(icons)} icons, {len(ORGS)} orgs, {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "package")
