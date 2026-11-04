"""maimai DX rating: single-chart rating and Best 50, with the per-server rules in data/versions.json.

See docs/rating.md for the formula, its sources and the rule history.
Run `python3 rating.py` for a self-check against values from DXRating's tests and Diving-Fish's formula.
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# (lowest achievement %, coefficient, rank). Identical in DXRating, Diving-Fish and mai-tools (whose factors are these / 100).
# The x.9999 rows are the top of a rank: e.g. 100.4999% gives 22.2, not SSS's 21.6.
COEFFICIENTS = [
    (0, 0.0, "D"), (10, 1.6, "D"), (20, 3.2, "D"), (30, 4.8, "D"), (40, 6.4, "D"),
    (50, 8.0, "C"), (60, 9.6, "B"), (70, 11.2, "BB"), (75, 12.0, "BBB"), (79.9999, 12.8, "BBB"),
    (80, 13.6, "A"), (90, 15.2, "AA"), (94, 16.8, "AAA"), (96.9999, 17.6, "AAA"),
    (97, 20.0, "S"), (98, 20.3, "S+"), (98.9999, 20.6, "S+"), (99, 20.8, "SS"),
    (99.5, 21.1, "SS+"), (99.9999, 21.4, "SS+"), (100, 21.6, "SSS"), (100.4999, 22.2, "SSS"),
    (100.5, 22.4, "SSS+"),
]
ACHIEVEMENT_CAP = 100.5  # anything above SSS+ rates as 100.5%
AP_COMBOS = {"ap", "app"}


def _row(achievement):
    units = round(achievement * 10000)
    row = COEFFICIENTS[0]
    for r in COEFFICIENTS:
        if units >= round(r[0] * 10000):
            row = r
    return row


def rank_of(achievement):
    return _row(achievement)[2]


def chart_rating(constant, achievement, combo=None, ap_bonus=False):
    """floor(constant × coefficient × min(achievement, 100.5) / 100), plus 1 for AP/AP+ when the rule has the AP bonus.

    Computed in integers (constant in 0.1, achievement in 0.0001%, coefficient in 0.1) so that no float rounding
    lands a result on the wrong side of an integer.
    """
    units = min(round(achievement * 10000), round(ACHIEVEMENT_CAP * 10000))
    coefficient = _row(achievement)[1]
    base = round(constant * 10) * units * round(coefficient * 10) // 100_000_000
    return base + (1 if ap_bonus and combo in AP_COMBOS else 0)


def min_achievement(constant, rating):
    """Lowest achievement (to 0.0001%) whose rating (without AP bonus) is at least `rating`, or None if unreachable."""
    lo, hi = 0, round(ACHIEVEMENT_CAP * 10000)
    if chart_rating(constant, hi / 10000) < rating:
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if chart_rating(constant, mid / 10000) >= rating:
            hi = mid
        else:
            lo = mid + 1
    return lo / 10000


def best50(scores, ap_bonus):
    """Split scores into the new (B15) and old (B35) frames and sum them.

    `scores`: dicts with `chart` (any key unique to a chart), `constant`, `achievement`, `is_new`, optional `combo`.
    Only the best score of each chart counts. Ties are broken by achievement, as DXRating and Diving-Fish do.
    """
    best = {}
    for s in scores:
        rated = {**s, "rating": chart_rating(s["constant"], s["achievement"], s.get("combo"), ap_bonus)}
        prev = best.get(s["chart"])
        if prev is None or (rated["rating"], rated["achievement"]) > (prev["rating"], prev["achievement"]):
            best[s["chart"]] = rated
    order = lambda s: (-s["rating"], -s["achievement"])  # noqa: E731
    new = sorted((s for s in best.values() if s["is_new"]), key=order)[:15]
    old = sorted((s for s in best.values() if not s["is_new"]), key=order)[:35]
    return {
        "rating": sum(s["rating"] for s in new) + sum(s["rating"] for s in old),
        "new": new,
        "old": old,
    }


DEFAULT_SERVER = "cn"


def load_rule(server=DEFAULT_SERVER):
    """{'current': ..., 'rule': {'new_versions': [...], 'ap_bonus': bool}, ...} for 'jp' or 'cn'."""
    return json.loads((DATA / "versions.json").read_text(encoding="utf-8"))[server]


def load_charts(server=DEFAULT_SERVER):
    return json.loads((DATA / server / "charts.json").read_text(encoding="utf-8"))


def _self_check():
    # from gekichumai/dxrating apps/backend/src/services/mcp/rating.test.ts
    assert chart_rating(15, 100.5) == 337
    assert chart_rating(15, 101.0) == 337
    assert chart_rating(13.4, 100.4999) == 298 and rank_of(100.4999) == "SSS"
    assert chart_rating(13.4, 100.5, "ap", ap_bonus=True) == chart_rating(13.4, 100.5) + 1
    assert chart_rating(13.4, 100.5, "ap", ap_bonus=False) == chart_rating(13.4, 100.5)
    a = min_achievement(13.4, 290)
    assert chart_rating(13.4, a) >= 290 > chart_rating(13.4, a - 0.0001)
    assert min_achievement(13.4, 299) == 100.5 and min_achievement(13.4, 400) is None

    # Diving-Fish's formula, int(c * ds * min(100.5, a) / 100) in floats, over every CN constant and many achievements
    def df(ds, a):
        c = [r for r in COEFFICIENTS if a >= r[0]][-1][1]
        return int(c * ds * min(100.5, a) / 100)

    constants = sorted({c["constant"] for c in load_charts("cn")})
    achievements = [x / 10000 for x in range(800000, 1010001, 37)] + [r[0] for r in COEFFICIENTS]
    diffs = [(c, a, chart_rating(c, a), df(c, a)) for c in constants for a in achievements
             if chart_rating(c, a) != df(c, a)]
    print(f"vs Diving-Fish float formula: {len(constants) * len(achievements):,} cases, {len(diffs)} differ"
          + (f", e.g. {diffs[:3]} (float rounding)" if diffs else ""))
    print("self-check ok")


if __name__ == "__main__":
    _self_check()
