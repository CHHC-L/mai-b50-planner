#!/usr/bin/env python3
"""Fetch maimai DX chart data (JP + CN) and build normalized chart lists.

Sources (see docs/rating.md for why each one):
  JP: DXRating catalog  https://miruku.dxrating.net/api/v1/dxdata
      (fallback: the snapshot committed in github.com/gekichumai/dxrating)
  CN: LXNS (落雪查分器)  https://maimai.lxns.net/api/v0/maimai/song/list[?version=N]
      Diving-Fish (水鱼)  https://www.diving-fish.com/api/maimaidxprober/{music_data,chart_stats}

Usage:
  python3 scripts/update_data.py            # download into data/raw/, then build
  python3 scripts/update_data.py --offline  # rebuild from data/raw/ only
  python3 scripts/update_data.py --strict   # fail (exit 1) on a game version this script does not know yet

Outputs:
  data/versions.json   version tables, current version and rating rule per server
  data/jp/charts.json  every rateable chart playable in JP, with constants by version
  data/cn/charts.json  every rateable chart playable in CN, with constants by CN version
  web/data/charts-cn.json  the CN chart list the web page loads (compact, no player data)
"""
import argparse
import json
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

DXRATING_API = "https://miruku.dxrating.net/api/v1/dxdata"
DXRATING_SNAPSHOT = "https://raw.githubusercontent.com/gekichumai/dxrating/main/packages/dxdata/snapshot.json"
LXNS_SONGS = "https://maimai.lxns.net/api/v0/maimai/song/list"
DF_MUSIC = "https://www.diving-fish.com/api/maimaidxprober/music_data"
DF_STATS = "https://www.diving-fish.com/api/maimaidxprober/chart_stats"

DIFFICULTIES = ["basic", "advanced", "expert", "master", "remaster"]

# JP version ids as used by DXRating / mai-tools / arcade-songs (VERSION_ID_MAP)
JP_VERSIONS = [
    "maimai", "maimai PLUS", "GreeN", "GreeN PLUS", "ORANGE", "ORANGE PLUS", "PiNK", "PiNK PLUS",
    "MURASAKi", "MURASAKi PLUS", "MiLK", "MiLK PLUS", "FiNALE", "maimaiでらっくす", "maimaiでらっくす PLUS",
    "Splash", "Splash PLUS", "UNiVERSE", "UNiVERSE PLUS", "FESTiVAL", "FESTiVAL PLUS", "BUDDiES", "BUDDiES PLUS",
    "PRiSM", "PRiSM PLUS", "CiRCLE", "CiRCLE PLUS", "MAGiCAL",
]
CIRCLE_ID = JP_VERSIONS.index("CiRCLE")
STRICT = False  # --strict: an unknown CN version is an error, not a warning (for unattended runs)

# The JP game version each CN version runs on. Rating rules follow the game version, so this decides the CN rule.
# From Yuri-YuzuChaN/maimaiDX constants.DX_CN_VERSION and Diving-Fish's `from` labels; constants of each CN version
# also match the JP version on the right (checked by this script, see "cn constant basis" in its output).
CN_JP_BASIS = {
    "舞萌DX": "maimaiでらっくす",
    "舞萌DX 2021": "Splash",
    "舞萌DX 2022": "UNiVERSE",
    "舞萌DX 2023": "FESTiVAL",
    "舞萌DX 2024": "BUDDiES",
    "舞萌DX 2025": "PRiSM",
    "舞萌DX 2026": "PRiSM PLUS",
}


def log(*args):
    print(*args, file=sys.stderr)


def fetch(url, dest, timeout=600):
    req = urllib.request.Request(url, headers={"User-Agent": "mai-rating-planner/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    json.loads(body)  # refuse to save anything that is not JSON
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    log(f"  {dest.relative_to(ROOT)}  {len(body):,} bytes")


def download():
    log("downloading sources ...")
    try:
        fetch(DXRATING_API, RAW / "dxrating" / "catalog.json")
    except Exception as e:  # the API is slow from some networks; the committed snapshot is a few days behind at most
        log(f"  DXRating API failed ({e}); using the GitHub snapshot")
        fetch(DXRATING_SNAPSHOT, RAW / "dxrating" / "catalog.json")
    fetch(LXNS_SONGS, RAW / "lxns" / "song_list.json")
    lxns = load(RAW / "lxns" / "song_list.json")
    dx_versions = [v["version"] for v in lxns["versions"] if v["version"] >= 20000]
    for code in dx_versions[:-1]:  # the last one is the current list
        fetch(f"{LXNS_SONGS}?version={code}", RAW / "lxns" / f"song_list_v{code}.json")
    fetch(DF_MUSIC, RAW / "divingfish" / "music_data.json")
    fetch(DF_STATS, RAW / "divingfish" / "chart_stats.json")
    (RAW / "fetched_at.txt").write_text(datetime.now(timezone.utc).isoformat(timespec="seconds") + "\n")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def norm_title(title):
    return unicodedata.normalize("NFKC", title).replace(" ", "").lower()


def write_rows(path, rows):
    """One chart per line: compact, but still diffable between updates."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n")
        f.write(",\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
        f.write("\n]\n")
    log(f"  wrote {path.relative_to(ROOT)}  ({len(rows)} charts)")


def jp_rule(version_name):
    vid = JP_VERSIONS.index(version_name)
    since_circle = vid >= CIRCLE_ID
    return {
        "new_versions": JP_VERSIONS[vid - 1: vid + 1][::-1] if since_circle else [version_name],
        "ap_bonus": since_circle,
    }


def build_jp(catalog):
    current = catalog["versions"][-1]["version"]
    if current not in JP_VERSIONS:
        sys.exit(f"error: unknown JP version {current}: add it to JP_VERSIONS")
    rule = jp_rule(current)
    rows = []
    for song in catalog["songs"]:
        for sh in song["sheets"]:
            if sh["type"] not in ("dx", "std") or "jp" not in sh["serverIds"]:
                continue
            history = dict(sorted((sh.get("multiverInternalLevelValue") or {}).items(),
                                  key=lambda kv: JP_VERSIONS.index(kv[0])))
            # DXRating's rule: a version's constant is its multiver entry, else the sheet's internalLevelValue
            constant = history.get(current, sh["internalLevelValue"])
            history[current] = constant
            iid = sh.get("internalId")
            rows.append({
                "id": sh["id"],
                "song_id": song["id"],
                "music_id": iid % 10000 if iid is not None else None,
                "title": song["title"],
                "artist": song["artist"],
                "genre": song["category"],
                "type": sh["type"],
                "difficulty": sh["difficulty"],
                "level": sh["level"],
                "constant": constant,
                "version": sh["version"],
                "release_date": sh.get("releaseDate"),
                "is_new": sh["version"] in rule["new_versions"],
                "history": history,
            })
    rows.sort(key=lambda r: (-r["constant"], r["title"], r["type"], DIFFICULTIES.index(r["difficulty"])))
    return current, rule, rows


def lxns_charts(song_list):
    for s in song_list["songs"]:
        for t in ("standard", "dx"):
            for c in s["difficulties"].get(t, []):
                yield s, ("std" if t == "standard" else "dx"), c


def cn_version_name(code, cn_versions):
    name = None
    for v in cn_versions:
        if v["version"] <= code:
            name = v["title"]
    return name


def build_cn(lxns, lxns_history, df_music, df_stats, jp_rows):
    cn_versions = [v for v in lxns["versions"] if v["version"] >= 20000]
    current = cn_versions[-1]
    current_name = current["title"]
    basis = CN_JP_BASIS.get(current_name)
    if basis is None:
        msg = f"unknown CN version {current_name}: add it to CN_JP_BASIS"
        if STRICT:
            sys.exit(f"error: {msg}")
        log(f"  !! {msg}; assuming pre-CiRCLE rules")
    rule = jp_rule(basis) if basis else {"new_versions": [current_name], "ap_bonus": False}
    if rule["ap_bonus"]:  # a CiRCLE-based CN version: new = this CN version + the previous CN version
        new_codes = (cn_versions[-2]["version"], 10 ** 9)
    else:
        new_codes = (current["version"], 10 ** 9)

    # constants of each past CN version, from LXNS ?version=
    hist = {}
    for v in cn_versions[:-1]:
        data = lxns_history.get(v["version"])
        if not data:
            continue
        for s, t, c in lxns_charts(data):
            hist.setdefault((s["id"], t, c["difficulty"]), {})[v["title"]] = c["level_value"]

    # Diving-Fish: fitted difficulty (拟合定数) from its players' scores, and its version label
    stats = df_stats.get("charts", {})
    df_from = {}
    for m in df_music:
        mid = int(m["id"])
        if mid < 100000:
            df_from[mid % 10000] = m["basic_info"]["from"]

    # JP cross-reference by music id, then by title
    jp_by_key = {}
    jp_song_by_mid, jp_song_by_title = {}, {}
    for r in jp_rows:
        jp_by_key[(r["song_id"], r["type"], r["difficulty"])] = r
        if r["music_id"] is not None:
            jp_song_by_mid.setdefault(r["music_id"], {})[norm_title(r["title"])] = r["song_id"]
        jp_song_by_title.setdefault(norm_title(r["title"]), set()).add(r["song_id"])

    def jp_song_for(mid, title):
        by_mid = jp_song_by_mid.get(mid, {})
        if norm_title(title) in by_mid:
            return by_mid[norm_title(title)]
        cands = jp_song_by_title.get(norm_title(title), set())
        return next(iter(cands)) if len(cands) == 1 else None

    rows, unmatched_jp = [], set()
    for s, t, c in lxns_charts(lxns):
        diff = DIFFICULTIES[c["difficulty"]]
        df_id = s["id"] + (10000 if t == "dx" else 0)
        st = stats.get(str(df_id), [])
        st = st[c["difficulty"]] if c["difficulty"] < len(st) else {}
        jp_song = jp_song_for(s["id"], s["title"])
        if jp_song is None:
            unmatched_jp.add((s["id"], s["title"]))
        jp = jp_by_key.get((jp_song, t, diff)) if jp_song else None
        history = dict(hist.get((s["id"], t, c["difficulty"]), {}))
        history[current_name] = c["level_value"]
        rows.append({
            "music_id": s["id"],
            "title": s["title"],
            "artist": s["artist"],
            "genre": s["genre"],
            "type": t,
            "difficulty": diff,
            "level": c["level"],
            "constant": c["level_value"],
            "version_code": c["version"],
            "version": cn_version_name(c["version"], lxns["versions"]),
            "df_version_label": df_from.get(s["id"]),
            "release_date": c.get("release_date"),
            "is_new": new_codes[0] <= c["version"] < new_codes[1],
            "history": history,
            "fit_diff": round(st["fit_diff"], 3) if st.get("fit_diff") is not None else None,
            "df_play_count": int(st["cnt"]) if st.get("cnt") is not None else None,
            "jp_id": jp["id"] if jp else None,
            "jp_constant": jp["constant"] if jp else None,
        })
    rows.sort(key=lambda r: (-r["constant"], r["title"], r["type"], DIFFICULTIES.index(r["difficulty"])))
    if unmatched_jp:
        log(f"  {len(unmatched_jp)} CN songs without a JP match (CN-only or renamed): "
            f"{sorted(unmatched_jp)[:8]}{' ...' if len(unmatched_jp) > 8 else ''}")
    return current_name, basis, rule, cn_versions, rows


def check_cn_sources(lxns, df_music):
    """LXNS and Diving-Fish are independent CN sources; report where they disagree."""
    lx = {(s["id"], t, c["difficulty"]): c["level_value"] for s, t, c in lxns_charts(lxns)}
    diff, both = [], 0
    for m in df_music:
        mid = int(m["id"])
        if mid >= 100000:
            continue
        t = "dx" if m["type"] == "DX" else "std"
        for i, ds in enumerate(m["ds"]):
            k = (mid % 10000, t, i)
            if k in lx:
                both += 1
                if abs(lx[k] - ds) > 1e-9:
                    diff.append((m["title"], t, DIFFICULTIES[i], ds, lx[k]))
    log(f"  cn sources: {both} charts in both LXNS and Diving-Fish, {len(diff)} constant mismatches"
        f"{': ' + str(diff[:5]) if diff else ''}; LXNS-only charts: {len(lx) - both}")


def check_cn_basis(lxns_history, lxns, cn_versions, jp_catalog):
    """For each CN version, the share of charts whose CN constant equals the JP constant of the mapped version."""
    jp = {}
    for song in jp_catalog["songs"]:
        for sh in song["sheets"]:
            if sh["type"] in ("dx", "std") and sh.get("internalId") is not None:
                jp[(sh["internalId"] % 10000, sh["type"], DIFFICULTIES.index(sh["difficulty"]))] = \
                    sh.get("multiverInternalLevelValue") or {}
    for v in cn_versions:
        data = lxns if v is cn_versions[-1] else lxns_history.get(v["version"])
        basis = CN_JP_BASIS.get(v["title"])
        if not data or not basis:
            continue
        same = n = 0
        for s, t, c in lxns_charts(data):
            mv = jp.get((s["id"], t, c["difficulty"]), {})
            if basis in mv:
                n += 1
                same += abs(mv[basis] - c["level_value"]) < 1e-9
        if n:
            log(f"  cn constant basis: {v['title']} vs JP {basis}: {same}/{n} equal ({same / n:.1%})")


def write_web_catalog(cn, cn_rows, fetched_at):
    """The chart list the static web page loads: one array per chart, no player data."""
    rows = [[f'{r["music_id"]}:{r["type"]}:{r["difficulty"]}', r["title"], r["type"], r["difficulty"], r["level"],
             r["constant"], r["fit_diff"] if (r["df_play_count"] or 0) >= 50 else None, r["is_new"], r["version"],
             r["release_date"]] for r in cn_rows]
    doc = {"server": "cn", "version": cn["current"], "newVersions": cn["rule"]["new_versions"],
           "apBonus": cn["rule"]["ap_bonus"], "fetchedAt": fetched_at, "charts": rows}
    out = ROOT / "web" / "data" / "charts-cn.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    log(f"  wrote {out.relative_to(ROOT)}  ({len(rows)} charts, {out.stat().st_size:,} bytes)")


def build():
    catalog = load(RAW / "dxrating" / "catalog.json")
    lxns = load(RAW / "lxns" / "song_list.json")
    lxns_history = {int(p.stem.rsplit("_v", 1)[1]): load(p) for p in sorted((RAW / "lxns").glob("song_list_v*.json"))}
    df_music = load(RAW / "divingfish" / "music_data.json")
    df_stats = load(RAW / "divingfish" / "chart_stats.json")
    fetched_at = (RAW / "fetched_at.txt").read_text().strip() if (RAW / "fetched_at.txt").exists() else None

    log("building ...")
    jp_current, jp_rule_now, jp_rows = build_jp(catalog)
    cn_current, cn_basis, cn_rule_now, cn_versions, cn_rows = build_cn(lxns, lxns_history, df_music, df_stats, jp_rows)
    check_cn_sources(lxns, df_music)
    check_cn_basis(lxns_history, lxns, cn_versions, catalog)

    cn_first_dates = {}
    for r in cn_rows:
        if r["release_date"] and r["version"]:
            d = cn_first_dates.get(r["version"])
            cn_first_dates[r["version"]] = min(d, r["release_date"]) if d else r["release_date"]

    versions = {
        "fetched_at": fetched_at,
        "sources": {
            "jp": {"dxrating_catalog_updated_at": catalog.get("updatedAt")},
            "cn": {"lxns_history_versions": sorted(lxns_history)},
        },
        "jp": {
            "current": jp_current,
            "rule": jp_rule_now,
            "versions": [
                {"id": JP_VERSIONS.index(v["version"]), "name": v["version"], "abbr": v.get("abbr"),
                 "release_date": v.get("releaseDate")}
                for v in catalog["versions"]
            ],
        },
        "cn": {
            "current": cn_current,
            "jp_basis": cn_basis,
            "rule": {"new_versions": [r for r in sorted({x["version"] for x in cn_rows if x["is_new"]})],
                     "ap_bonus": cn_rule_now["ap_bonus"]},
            "versions": [
                {"code": v["version"], "name": v["title"], "jp_basis": CN_JP_BASIS.get(v["title"]),
                 "first_chart_release_date": cn_first_dates.get(v["title"])}
                for v in cn_versions
            ],
        },
    }
    out = ROOT / "data" / "versions.json"
    out.write_text(json.dumps(versions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"  wrote {out.relative_to(ROOT)}")
    write_rows(ROOT / "data" / "jp" / "charts.json", jp_rows)
    write_rows(ROOT / "data" / "cn" / "charts.json", cn_rows)
    write_web_catalog(versions["cn"], cn_rows, fetched_at)
    log(f"JP: {jp_current}, {len(jp_rows)} charts, {sum(r['is_new'] for r in jp_rows)} new "
        f"(B15 versions {jp_rule_now['new_versions']}, AP bonus {jp_rule_now['ap_bonus']})")
    log(f"CN: {cn_current} (game basis JP {cn_basis}), {len(cn_rows)} charts, {sum(r['is_new'] for r in cn_rows)} new "
        f"(AP bonus {cn_rule_now['ap_bonus']})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="rebuild from data/raw/ without downloading")
    ap.add_argument("--strict", action="store_true", help="fail on a game version this script does not know yet")
    args = ap.parse_args()
    global STRICT
    STRICT = args.strict
    if not args.offline:
        download()
    build()


if __name__ == "__main__":
    main()
