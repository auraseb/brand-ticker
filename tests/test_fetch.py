import pytest

from brand_ticker import fetch


def hit(owner, repo="r", stars=500, kind="Organization", private=False):
    return {"repository": {"nameWithOwner": f"{owner}/{repo}", "stargazerCount": stars, "isPrivate": private,
                           "owner": {"__typename": kind, "login": owner, "avatarUrl": f"https://a/{owner}"}}}


def test_collect_keeps_public_orgs_over_the_star_floor():
    nodes = [hit("vercel", "next.js", 130000), hit("vercel", "swr", 30000), hit("Apple", "pkl", 10000),
             hit("tiny", stars=12), hit("someone", kind="User"), hit("secret", private=True), {}, None,
             hit("me"), hit("skipme")]
    got = fetch.collect(nodes, "me", 100, {"skipme"})
    assert set(got) == {"vercel", "apple"}
    assert got["vercel"]["hits"] == 2 and got["vercel"]["stars"] == 130000
    assert got["vercel"]["repos"] == ["vercel/next.js", "vercel/swr"]
    assert got["apple"]["login"] == "Apple"


def test_search_query_modes():
    assert fetch.search_query("ann", "prs_and_issues") == "author:ann -user:ann is:public sort:created-desc"
    assert fetch.search_query("ann", "merged_prs").endswith("is:pr is:merged")
    with pytest.raises(SystemExit):
        fetch.search_query("ann", "stars")


def test_rank_pins_first_then_fame(monkeypatch):
    found = {k: {"login": k, "stars": s} for k, s in [("a", 10), ("b", 5000), ("c", 300), ("d", 300)]}
    monkeypatch.setattr(fetch, "fame", lambda logins, token: {"a": 900, "b": 100, "c": 50000, "d": 50000})
    order = [e["login"] for e in fetch.rank(found, "t", first=["b", "zzz"])]
    assert order == ["b", "c", "d", "a"]


def test_contributions_reads_the_profile_number(monkeypatch):
    page = '<h2 class="f4">\n      3,268\n      contributions\n        in the last year\n    </h2>'
    monkeypatch.setattr(fetch, "http", lambda url, *a, **k: page.encode())
    assert fetch.contributions("x") == 3268


def test_contributions_falls_back_to_graphql(monkeypatch):
    def boom(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(fetch, "http", boom)
    monkeypatch.setattr(fetch, "graphql", lambda q, v, t: {"user": {"contributionsCollection": {
        "contributionCalendar": {"totalContributions": 41}}}})
    assert fetch.contributions("x", "t") == 41
