"""Import a player's scores from LXNS (落雪) or Diving-Fish (水鱼), and match them to data/<server>/charts.json.

Usage:
  python3 scores.py lxns                         # personal API key: --token, $LXNS_TOKEN or secrets.json "lxns_token"
  python3 scores.py divingfish                   # Import-Token: --import-token, $DF_IMPORT_TOKEN or "df_import_token"
  python3 scores.py divingfish --username NAME   # no token: public B50 only (if the player allows it)
  python3 scores.py show data/player/lxns.json   # re-check a saved import

Each import is saved to data/player/<source>.json and summarized: the B50 recomputed from our chart data next to the
rating the source reports. Both sources are CN servers, so scores are matched against the CN chart list.

Scores a source cannot see (e.g. on songs locked for the account, which the score pages do not list) go in
data/player/manual.json, a list of {"title", "type": "dx"|"std", "difficulty", "achievement", "combo"?, "note"?}
("music_id" may replace "title"). They are merged into every import: per chart, the higher achievement wins.

Where the tokens come from:
  LXNS:        maimai.lxns.net → 账号设置 → 个人 API 密钥 (sent as X-User-Token; read-only is enough)
  Diving-Fish: www.diving-fish.com/maimaidx/prober → 编辑个人资料 → Import-Token (sent as Import-Token)
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import rating

ROOT = Path(__file__).resolve().parent
PLAYER_DIR = ROOT / "data" / "player"
SECRETS = ROOT / "secrets.json"
MANUAL = PLAYER_DIR / "manual.json"
SOURCES = ("lxns", "divingfish")  # saved imports are data/player/<source>.json

LXNS_API = "https://maimai.lxns.net/api/v0/user/maimai/player"
DF_API = "https://www.diving-fish.com/api/maimaidxprober"

DIFFICULTIES = ["basic", "advanced", "expert", "master", "remaster"]


class ImportError_(Exception):
    pass


def _request(url, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "mai-rating-planner/0.1",
        **({"Content-Type": "application/json"} if data else {}),
        **(headers or {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ImportError_(f"{url}: HTTP {e.code} {detail}") from None


def _secret(name, env):
    if os.environ.get(env):
        return os.environ[env]
    if SECRETS.exists():
        return json.loads(SECRETS.read_text()).get(name)
    return None


def _profile(source, name, reported_rating, scores, complete):
    return {
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "complete": complete,  # False when only the B50 was available
        "player": {"name": name, "rating": reported_rating},
        "scores": scores,
    }


def fetch_lxns(token):
    """All scores of the player who owns the personal API key."""
    def get(path):
        resp = _request(LXNS_API + path, {"X-User-Token": token})
        if not resp.get("success"):
            raise ImportError_(f"LXNS {path or '/'}: {resp.get('code')} {resp.get('message')}")
        return resp["data"]

    player = get("")
    scores = []
    for s in get("/scores"):
        if s["type"] == "utage":
            continue
        scores.append({
            "music_id": s["id"] % 10000,
            "type": "std" if s["type"] == "standard" else "dx",
            "difficulty": DIFFICULTIES[s["level_index"]],
            "title": s["song_name"],
            "level": s["level"],
            "achievement": s["achievements"],
            "combo": s.get("fc"),
            "sync": s.get("fs"),
            "dx_score": s.get("dx_score"),
            "played_at": s.get("last_played_time") or s.get("play_time"),
        })
    return _profile("lxns", player["name"], player["rating"], scores, complete=True)


def _df_scores(records):
    scores = []
    for r in records:
        if r["song_id"] >= 100000:  # utage
            continue
        scores.append({
            "music_id": r["song_id"] % 10000,
            "type": "dx" if r["type"] == "DX" else "std",
            "difficulty": DIFFICULTIES[r["level_index"]],
            "title": r["title"],
            "level": r["level"],
            "achievement": r["achievements"],
            "combo": r.get("fc") or None,
            "sync": r.get("fs") or None,
            "dx_score": r.get("dxScore"),
            "played_at": None,
        })
    return scores


def fetch_divingfish(import_token=None, username=None):
    """All scores with the player's Import-Token; with only a username, the public B50."""
    if import_token:
        data = _request(f"{DF_API}/player/records", {"Import-Token": import_token})
        return _profile("divingfish", data.get("nickname") or data.get("username"), data.get("rating"),
                        _df_scores(data["records"]), complete=True)
    if username:
        data = _request(f"{DF_API}/query/player", body={"username": username, "b50": "1"})
        records = data["charts"]["dx"] + data["charts"]["sd"]
        return _profile("divingfish", data.get("nickname") or username, data.get("rating"),
                        _df_scores(records), complete=False)
    raise ImportError_("Diving-Fish needs an Import-Token or a username")


def with_manual(profile, server=rating.DEFAULT_SERVER):
    """The profile with data/player/manual.json merged in: per chart, the higher achievement wins."""
    if not MANUAL.exists():
        return profile
    charts = rating.load_charts(server)
    by_title = {}
    for c in charts:
        by_title.setdefault((c["title"], c["type"], c["difficulty"]), c)
    merged = {(s["music_id"], s["type"], s["difficulty"]): s for s in profile["scores"]}
    used = 0
    for m in json.loads(MANUAL.read_text(encoding="utf-8")):
        if "music_id" in m:
            mid = m["music_id"]
        else:
            c = by_title.get((m["title"], m["type"], m["difficulty"]))
            if c is None:
                raise ImportError_(f"manual.json: no {m['type']} {m['difficulty']} chart titled {m['title']!r}")
            mid = c["music_id"]
        key = (mid, m["type"], m["difficulty"])
        old = merged.get(key)
        if old is None or m["achievement"] > old["achievement"]:
            merged[key] = {
                "music_id": mid, "type": m["type"], "difficulty": m["difficulty"],
                "title": m.get("title") or (old or {}).get("title"), "level": (old or {}).get("level"),
                "achievement": m["achievement"], "combo": m.get("combo"), "sync": m.get("sync"),
                "dx_score": None, "played_at": None, "manual": True,
            }
            used += 1
    return {**profile, "scores": list(merged.values()), "manual_used": used}


def load_profile(source=None):
    """A saved import (the newest complete one if `source` is None), with manual.json merged in."""
    paths = [PLAYER_DIR / f"{s}.json" for s in ([source] if source else SOURCES)]
    profiles = [json.loads(p.read_text(encoding="utf-8")) for p in paths if p.exists()]
    if not profiles:
        raise ImportError_(f"no saved import in {PLAYER_DIR.relative_to(ROOT)}; run `python3 scores.py lxns` first")
    profiles.sort(key=lambda p: (p["complete"], p["fetched_at"]))
    return with_manual(profiles[-1])


def match(scores, server=rating.DEFAULT_SERVER):
    """Attach constant and is_new from our chart list. Returns (matched, unmatched)."""
    charts = {(c["music_id"], c["type"], c["difficulty"]): c for c in rating.load_charts(server)}
    matched, unmatched = [], []
    for s in scores:
        key = (s["music_id"], s["type"], s["difficulty"])
        c = charts.get(key)
        if c is None:
            unmatched.append(s)
        else:
            matched.append({**s, "chart": key, "constant": c["constant"], "is_new": c["is_new"]})
    return matched, unmatched


def summarize(profile, server=rating.DEFAULT_SERVER):
    profile = with_manual(profile, server)
    rule = rating.load_rule(server)
    matched, unmatched = match(profile["scores"], server)
    b50 = rating.best50(matched, rule["rule"]["ap_bonus"])
    new_sum = sum(s["rating"] for s in b50["new"])
    old_sum = sum(s["rating"] for s in b50["old"])
    p = profile["player"]
    print(f"{profile['source']}: {p['name']}, {len(profile['scores'])} scores "
          f"({'all' if profile['complete'] else 'B50 only'}), fetched {profile['fetched_at']}")
    if profile.get("manual_used"):
        print(f"  + {profile['manual_used']} scores from {MANUAL.relative_to(ROOT)}")
    print(f"  rating reported by source: {p['rating']}")
    print(f"  recomputed ({server} {rule['current']}): {b50['rating']} = B15 {new_sum} + B35 {old_sum}"
          f"  (B15 floor {b50['new'][-1]['rating'] if b50['new'] else '-'},"
          f" B35 floor {b50['old'][-1]['rating'] if b50['old'] else '-'})")
    if unmatched:
        print(f"  {len(unmatched)} scores not in data/{server}/charts.json (removed songs, or chart data is older "
              f"than the scores): {[s['title'] + ' ' + s['difficulty'] for s in unmatched[:5]]}")
    return b50


def save(profile):
    PLAYER_DIR.mkdir(parents=True, exist_ok=True)
    path = PLAYER_DIR / f"{profile['source']}.json"
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  saved {path.relative_to(ROOT)}")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lx = sub.add_parser("lxns")
    lx.add_argument("--token")
    df = sub.add_parser("divingfish")
    df.add_argument("--import-token")
    df.add_argument("--username")
    sh = sub.add_parser("show")
    sh.add_argument("path")
    args = ap.parse_args()

    try:
        if args.cmd == "show":
            summarize(json.loads(Path(args.path).read_text(encoding="utf-8")))
            return
        if args.cmd == "lxns":
            token = args.token or _secret("lxns_token", "LXNS_TOKEN")
            if not token:
                sys.exit("no LXNS token: pass --token, set LXNS_TOKEN, or put lxns_token in secrets.json")
            profile = fetch_lxns(token)
        else:
            token = args.import_token or (None if args.username else _secret("df_import_token", "DF_IMPORT_TOKEN"))
            profile = fetch_divingfish(token, args.username)
    except ImportError_ as e:
        sys.exit(f"import failed: {e}")
    summarize(profile)
    save(profile)


if __name__ == "__main__":
    main()
