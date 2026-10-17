"""Everything that touches the network: the count, the orgs, their avatars."""
import json, os, re, ssl, time, urllib.error, urllib.request

GRAPHQL = "https://api.github.com/graphql"
UA = {"User-Agent": "brand-ticker"}

SEARCH = """query($q: String!, $after: String) {
  search(query: $q, type: ISSUE, first: 100, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest { repository { ...r } }
      ... on Issue { repository { ...r } }
    }
  }
}
fragment r on Repository { nameWithOwner stargazerCount isPrivate owner { __typename login avatarUrl(size: 460) } }"""

MODES = {
    "prs_and_issues": "",
    "merged_prs": " is:pr is:merged",
}


def _context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
        if os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


CTX = _context()


def http(url, data=None, headers=None, tries=3):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429 or attempt == tries - 1:
                raise
        except urllib.error.URLError:
            if attempt == tries - 1:
                raise
        time.sleep(2 * (attempt + 1))


def graphql(query, variables, token, partial=False):
    if not token:
        raise SystemExit("brand-ticker needs a token (GH_TOKEN, GITHUB_TOKEN or --token)")
    body = json.dumps({"query": query, "variables": variables}).encode()
    out = json.loads(http(GRAPHQL, body, {"Authorization": f"bearer {token}", "Content-Type": "application/json"}))
    if out.get("errors") and not (partial and out.get("data")):
        raise RuntimeError("GitHub GraphQL: " + "; ".join(e.get("message", "?") for e in out["errors"]))
    return out["data"]


def contributions(user, token=None):
    """The number on the profile: contributions in the last year, private ones included if the user shows them."""
    try:
        page = http(f"https://github.com/users/{user}/contributions").decode()
        m = re.search(r"([0-9][0-9,]*)\s+contributions?\s+in the last year", page)
        if m:
            return int(m.group(1).replace(",", ""))
    except Exception:
        pass
    q = 'query($u: String!) { user(login: $u) { contributionsCollection { contributionCalendar { totalContributions } } } }'
    return graphql(q, {"u": user}, token)["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]


def search_query(user, mode):
    if mode not in MODES:
        raise SystemExit(f"mode must be one of {', '.join(MODES)}")
    return f"author:{user} -user:{user} is:public sort:created-desc{MODES[mode]}"


def collect(nodes, user, min_stars, exclude, orgs=None):
    """Fold search hits into {login_lower: {login, avatar, stars, hits, repos}}. Orgs only, public only."""
    orgs = {} if orgs is None else orgs
    for n in nodes:
        r = (n or {}).get("repository")
        if not r or r.get("isPrivate") or r["stargazerCount"] < min_stars:
            continue
        o = r["owner"]
        low = o["login"].lower()
        if o["__typename"] != "Organization" or low in exclude or low == user.lower():
            continue
        e = orgs.setdefault(low, {"login": o["login"], "avatar": o["avatarUrl"], "stars": 0, "hits": 0, "repos": []})
        e["hits"] += 1
        e["stars"] = max(e["stars"], r["stargazerCount"])
        if r["nameWithOwner"] not in e["repos"]:
            e["repos"].append(r["nameWithOwner"])
    return orgs


def orgs(user, mode, token, min_stars=100, exclude=(), pages=10):
    """Every org the user opened issues or PRs in (or only merged PRs), from GitHub search (1,000 hits max)."""
    exclude = {e.lower() for e in exclude}
    q, after, found = search_query(user, mode), None, {}
    for _ in range(pages):
        s = graphql(SEARCH, {"q": q, "after": after}, token)["search"]
        collect(s["nodes"], user, min_stars, exclude, found)
        if not s["pageInfo"]["hasNextPage"]:
            break
        after = s["pageInfo"]["endCursor"]
    return found


def fame(logins, token):
    """Stars on each org's most starred public repo, one aliased query for all of them."""
    out = {}
    logins = list(logins)
    for i in range(0, len(logins), 50):
        chunk = logins[i:i + 50]
        parts = [f'o{j}: organization(login: {json.dumps(l)}) {{ repositories(first: 1, privacy: PUBLIC, '
                 f'orderBy: {{field: STARGAZERS, direction: DESC}}) {{ nodes {{ stargazerCount }} }} }}'
                 for j, l in enumerate(chunk)]
        try:
            data = graphql("query {" + " ".join(parts) + "}", {}, token, partial=True)
        except RuntimeError:
            data = {}
        for j, l in enumerate(chunk):
            nodes = ((data.get(f"o{j}") or {}).get("repositories") or {}).get("nodes") or []
            out[l] = nodes[0]["stargazerCount"] if nodes else 0
    return out


def rank(found, token, first=()):
    """Pinned orgs first, in the order given, then the biggest names: by their most starred repo."""
    score = fame([e["login"] for e in found.values()], token) if found else {}
    pins = [p.lower() for p in first if p.lower() in found]
    rest = sorted((k for k in found if k not in pins),
                  key=lambda k: (-score.get(found[k]["login"], 0), -found[k]["stars"], k))
    return [found[k] for k in pins + rest]


def avatar(url, login=None):
    """Avatar bytes. BRAND_TICKER_CACHE=<dir> keeps a copy per org, handy for local runs and tests."""
    cache = os.environ.get("BRAND_TICKER_CACHE")
    path = os.path.join(cache, f"{(login or 'x').lower()}.img") if cache and login else None
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    data = http(url)
    if path:
        os.makedirs(cache, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return data
