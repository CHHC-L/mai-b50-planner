"""Plan how to reach a target rating in the current version of a server, from the player's own scores.

Usage:
  python3 plan.py 16000                       # CN rules, newest import in data/player/ + manual.json
  python3 plan.py 16000 --source divingfish   # a specific import
  python3 plan.py 16000 --alternatives 20     # longer list of other options

How it decides (details in docs/planning.md):
  candidates  every released chart, at each rank line above the current score (S 97 … SSS+ 100.5) whose rating
              would raise the B50 total
  把握         the player's own record at that difficulty (水鱼拟合定数, or 定数): the share of their charts there
              that reached the line (a non-increasing fit over difficulty), given the line they already hold on this
              chart, raised when the current score is close to the line
  plan        greedy by B50 gain / -ln(把握), recomputing B15/B35 after each pick, until the target is reached
"""
import argparse
import math
import unicodedata
from datetime import date

import rating
import scores

LINES = [97.0, 98.0, 99.0, 99.5, 100.0, 100.5]
LINE_NAMES = {97.0: "S", 98.0: "S+", 99.0: "SS", 99.5: "SS+", 100.0: "SSS", 100.5: "SSS+"}
BAND = {97.0: 1.0, 98.0: 1.0, 99.0: 1.0, 99.5: 0.5, 100.0: 0.5, 100.5: 0.5}  # width of the band below each line
MIN_FIT_PLAYS = 50  # use 水鱼拟合定数 only with this many plays behind it
CHANCE_RANGE = (0.03, 0.97)
SKILL_POINTS = [13.0, 13.5, 14.0, 14.5, 15.0]


def chart_key(c):
    return (c["music_id"], c["type"], c["difficulty"])


def difficulty(chart):
    if chart.get("fit_diff") is not None and (chart.get("df_play_count") or 0) >= MIN_FIT_PLAYS:
        return chart["fit_diff"]
    return chart["constant"]


def _decreasing_fit(points):
    """Isotonic regression (pool adjacent violators): the best non-increasing step fit of y over x.
    Returns the blocks as (mean x, mean y), for linear interpolation between them."""
    blocks = []  # [sum_y, n, sum_x]
    for x, y in sorted(points):
        blocks.append([y, 1, x])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] < blocks[-1][0] / blocks[-1][1]:
            sy, n, sx = blocks.pop()
            blocks[-1][0] += sy
            blocks[-1][1] += n
            blocks[-1][2] += sx
    return [(sx / n, sy / n) for sy, n, sx in blocks]


def _interpolate(curve, x):
    if x <= curve[0][0]:
        return curve[0][1]
    for (x1, y1), (x2, y2) in zip(curve, curve[1:]):
        if x <= x2:
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    return curve[-1][1]


class Skill:
    """P(score ≥ line) as a function of difficulty, one non-increasing curve per rank line, from the player's best
    scores. A player's rates usually hold steady and then fall off a cliff, which a logistic curve smooths away.

    Only charts at or above `min_d` are used: easier charts are mostly played casually, which would make the curve
    rise with difficulty at the low end.
    """

    def __init__(self, samples, min_d):
        pts = [(d, a) for d, a in samples if d >= min_d]
        self.n = len(pts)
        self.curves = {line: _decreasing_fit([(d, 1.0 if a >= line else 0.0) for d, a in pts]) for line in LINES}

    def p(self, line, d):
        return _interpolate(self.curves[line], d)

    def chance(self, line, d, current=None):
        p = self.p(line, d)
        if current is not None:
            held = [l for l in LINES if current >= l]
            if held:  # given the line already reached on this chart
                p = min(1.0, p / max(self.p(held[-1], d), 1e-9))
            closeness = max(0.0, 1 - (line - current) / BAND[line])
            p += (1 - p) * closeness
        return min(max(p, CHANCE_RANGE[0]), CHANCE_RANGE[1])


def frames(state):
    """state: key -> (rating, is_new). Returns (total, {frame: (members, floor, full)})."""
    out, total = {}, 0
    for frame, size in (("new", 15), ("old", 35)):
        ranked = sorted(((r, k) for k, (r, new) in state.items() if new == (frame == "new")),
                        key=lambda x: x[0], reverse=True)[:size]
        total += sum(r for r, _ in ranked)
        out[frame] = ({k for _, k in ranked}, ranked[-1][0] if ranked else 0, len(ranked) == size)
    return total, out


def candidates(charts, best, state, fr, skill, planned):
    """Every (chart, line) that would raise the B50 total now, with its gain and chance."""
    floor_any = min(fr["new"][1] if fr["new"][2] else 0, fr["old"][1] if fr["old"][2] else 0)
    for c in charts:
        k = chart_key(c)
        if k in planned or rating.chart_rating(c["constant"], 100.5) <= floor_any:
            continue
        frame = "new" if c["is_new"] else "old"
        members, floor, full = fr[frame]
        cur = best.get(k)
        cur_rating = state[k][0] if k in state else 0
        for line in LINES:
            if cur is not None and cur >= line:
                continue
            r = rating.chart_rating(c["constant"], line)
            gain = r - cur_rating if k in members else (r - floor if full else r)
            if gain <= 0:
                continue
            ch = skill.chance(line, difficulty(c), cur)
            yield {"chart": c, "key": k, "frame": frame, "line": line, "current": cur, "from_rating": cur_rating,
                   "to_rating": r, "gain": gain, "chance": ch, "value": gain / -math.log(ch)}


def make_plan(charts, best, ratings_now, target, skill):
    state = dict(ratings_now)
    best = dict(best)
    planned, steps = set(), []
    total, fr = frames(state)
    while total < target:
        pick = max(candidates(charts, best, state, fr, skill, planned), key=lambda x: x["value"], default=None)
        if pick is None:
            break
        steps.append({**pick, "total_after": total + pick["gain"]})
        planned.add(pick["key"])
        best[pick["key"]] = pick["line"]
        state[pick["key"]] = (pick["to_rating"], pick["chart"]["is_new"])
        total, fr = frames(state)
    return steps, total


def width(s):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def fit(s, w):
    out = ""
    for ch in s:
        if width(out + ch) > w:
            break
        out += ch
    return out + " " * (w - width(out))


DIFF_SHORT = {"basic": "BAS", "advanced": "ADV", "expert": "EXP", "master": "MAS", "remaster": "ReM"}


def row(x, show_total=True):
    c = x["chart"]
    cur = f"{x['current']:.4f}" if x["current"] is not None else "未玩"
    total = f"{x['total_after']:>6}" if show_total else ""
    return (f"{'B15' if x['frame'] == 'new' else 'B35'}  {fit(c['title'], 26)} {'DX' if c['type'] == 'dx' else 'SD'} "
            f"{DIFF_SHORT[c['difficulty']]} {c['constant']:>4.1f} {difficulty(c):>5.2f}  {cur:>8} → "
            f"{LINE_NAMES[x['line']]:<4} {x['from_rating']:>3}→{x['to_rating']:<3} +{x['gain']:<3} "
            f"{x['chance']:>4.0%} {total}")


HEADER = "框   曲名                       类型 难度 定数  拟合      当前 → 目标  单曲      +分  把握"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", type=int, help="target rating")
    ap.add_argument("--source", choices=["lxns", "divingfish"], help="saved import to use (default: newest)")
    ap.add_argument("--alternatives", type=int, default=12, help="other options to list")
    args = ap.parse_args()
    args.server = "cn"  # the imported scores come from CN probers; planning for JP would need JP scores

    profile = scores.load_profile(args.source)
    info = rating.load_rule(args.server)
    today = date.today().isoformat()
    charts = [c for c in rating.load_charts(args.server) if (c["release_date"] or "") <= today]
    by_key = {chart_key(c): c for c in charts}
    matched, unmatched = scores.match(profile["scores"], args.server)
    best = {}
    for s in matched:
        best[s["chart"]] = max(best.get(s["chart"], 0), s["achievement"])
    ratings_now = {k: (rating.chart_rating(by_key[k]["constant"], a), by_key[k]["is_new"])
                   for k, a in best.items() if k in by_key}
    total, fr = frames(ratings_now)

    skill_min_d = min(by_key[k]["constant"] for k in fr["old"][0] | fr["new"][0]) - 0.5 if ratings_now else 13.0
    skill = Skill([(difficulty(by_key[k]), a) for k, a in best.items() if k in by_key], skill_min_d)

    rule = info["rule"]
    new_sum = sum(ratings_now[k][0] for k in fr["new"][0])
    print(f"服务器 {args.server}，当前版本 {info['current']}：B15 = {' + '.join(rule['new_versions'])} 的谱面，"
          f"AP {'加 1 分' if rule['ap_bonus'] else '不加分'}")
    print(f"成绩：{profile['source']} {profile['fetched_at'][:10]}，{len(best)} 张谱面"
          + (f"（含手动 {profile['manual_used']} 条）" if profile.get("manual_used") else ""))
    print(f"rating {total} = B15 {new_sum}（底线 {fr['new'][1]}）+ B35 {total - new_sum}（底线 {fr['old'][1]}）")
    print(f"你的水平（按拟合难度 ≥ {skill_min_d:.1f} 的 {skill.n} 张已玩谱面，各难度下达到该评级的比例）：")
    print("  拟合难度 " + "".join(f"{d:>7.1f}" for d in SKILL_POINTS))
    for line in (99.5, 100.0, 100.5):
        print(f"  {LINE_NAMES[line]:<8} " + "".join(f"{skill.p(line, d):>7.0%}" for d in SKILL_POINTS))
    if total >= args.target:
        print(f"已经达到 {args.target}。")
        return
    print(f"目标 {args.target}，还差 {args.target - total}\n")

    steps, final = make_plan(charts, best, ratings_now, args.target, skill)
    if not steps:
        print("没有能提高 rating 的谱面了。")
        return
    status = "达成" if final >= args.target else f"到 {final} 为止，仍差 {args.target - final}"
    print(f"推荐方案：{len(steps)} 张谱面，合计 +{final - total} → {final}（{status}）")
    print(f"{HEADER}  累计")
    for s in steps:
        print(row(s))
    n_unplayed = sum(1 for s in steps if s["current"] is None)
    print("\n把握是按你自己的成绩估的，只适合相互比较。"
          + (f"其中 {n_unplayed} 张你还没打过，可能需要先解锁。" if n_unplayed else ""))

    planned = {s["key"] for s in steps}
    others = sorted((x for x in candidates(charts, best, ratings_now, fr, skill, planned)),
                    key=lambda x: x["value"], reverse=True)
    seen, alt = set(), []
    for x in others:
        if x["key"] not in seen:
            seen.add(x["key"])
            alt.append(x)
        if len(alt) >= args.alternatives:
            break
    if alt:
        print(f"\n其他选择（按当前成绩单独计算的收益，前 {len(alt)} 张）")
        print(HEADER)
        for x in alt:
            print(row(x, show_total=False))
    if unmatched:
        print(f"\n{len(unmatched)} 条成绩不在谱面数据里，未计入。")


if __name__ == "__main__":
    try:
        main()
    except scores.ImportError_ as e:
        raise SystemExit(str(e))
