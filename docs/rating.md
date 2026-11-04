# maimai DX rating: rules, versions and data sources

## 1. Single-chart rating

```
rating = floor(constant × factor(achievement) × min(achievement, 100.5) / 100)   [+1, see the AP bonus]
```

The factor depends on the achievement band. The `x.9999` rows are the top of a rank and get a factor of their own:

| achievement ≥ | factor | rank |   | achievement ≥ | factor | rank |
|---|---|---|---|---|---|---|
| 100.5    | 22.4 | SSS+ |   | 94      | 16.8 | AAA |
| 100.4999 | 22.2 | SSS  |   | 90      | 15.2 | AA  |
| 100      | 21.6 | SSS  |   | 80      | 13.6 | A   |
| 99.9999  | 21.4 | SS+  |   | 79.9999 | 12.8 | BBB |
| 99.5     | 21.1 | SS+  |   | 75      | 12.0 | BBB |
| 99       | 20.8 | SS   |   | 70      | 11.2 | BB  |
| 98.9999  | 20.6 | S+   |   | 60      | 9.6  | B   |
| 98       | 20.3 | S+   |   | 50      | 8.0  | C   |
| 97       | 20.0 | S    |   | 40 / 30 / 20 / 10 / 0 | 6.4 / 4.8 / 3.2 / 1.6 / 0 | D |
| 96.9999  | 17.6 | AAA  |   |         |      |     |

- **Above SSS+**: an achievement above 100.5% counts as 100.5%, so nothing beyond SSS+ adds rating.
- **Examples**: constant 15.0 at SSS+ gives floor(15.0 × 22.4 × 100.5 / 100) = 337. Constant 13.4 at 100.4999%
  gives 298.
- **Integer maths**: `rating.py` and the web page compute in integers (constant in 0.1, achievement in 0.0001%,
  factor in 0.1), so no float rounding lands a result on the wrong side of an integer. Over every CN constant and
  about 5,700 achievements (541,405 cases), the results equal Diving-Fish's.
- **Sources**: the table is identical in DXRating (`packages/maimai-domain/src/best50.ts`), Diving-Fish
  (`web/src/scripts/ScoreCoefficient.js`) and mai-tools (`src/common/rank-functions.ts`, written as 0.224 etc.).

### AP bonus (from CiRCLE)

From **CiRCLE (JP, 2025-09-18)**, an AP or AP+ adds **1** to the chart's rating. FC adds nothing.

- **mai-tools** applies it from CiRCLE on (`rating-analyzer.ts`: `gameVer >= GameVersion.CiRCLE`). Its comment in
  `rating-functions.ts` reads "Since CiRCLE, All Perfect adds 1 point".
- **DXRating** applies it as well, but in every version, which is wrong before CiRCLE.
- **China server**: it currently runs on PRiSM PLUS, so there is **no AP bonus**. Diving-Fish's `recompute_ra.py` and
  `ScoreCoefficient` add none either.

## 2. Best 50

Rating = **best 15 charts of the new versions (B15)** + **best 35 of all other charts (B35)**.

- Only the best score of each chart counts. A song's DX and standard charts are different charts.
- Utage (宴) charts do not count.
- New or old is decided by the **chart's own version**: a DX chart or Re:MASTER added to an old song later counts as
  part of the version that added it.
- With fewer than 15 / 35 charts in a frame, the frame sums what it has.

### Which charts are "new"

| Game version | B15 counts | AP bonus |
|---|---|---|
| up to PRiSM PLUS | the current version | none |
| CiRCLE and later | the current version **and the previous one** | +1 |

- **Sources**: DXRating `best50.ts` (`isB15Sheet`, `useCircleB15`) and mai-tools (`isNewChart`,
  `includePreviousVerInNewCharts`) agree.
- **JP now (MAGiCAL)**: B15 = MAGiCAL + CiRCLE PLUS charts, with the AP bonus.
- **CN now (舞萌DX 2026, game version PRiSM PLUS)**: B15 = 舞萌DX 2026 charts only, no AP bonus. Diving-Fish's `is_new`
  and LXNS's version ≥ 25500 agree on every chart.

## 3. Version progress on the two servers

The China server runs about one and a half JP versions behind, and used to merge two JP versions into one. Which
rules apply depends on the JP **game version** a CN version runs on.

| CN version | LXNS code | JP version | First chart* | CN constants equal to that JP version's |
|---|---|---|---|---|
| 舞萌DX | 20000 | でらっくす (+PLUS) | 2019-12-05 | — |
| 舞萌DX 2021 | 21000 | Splash (+PLUS) | 2020-12-24 | 99.6% |
| 舞萌DX 2022 | 22000 | UNiVERSE (+PLUS) | 2022-06-23 | 89.4% (98.9% equal to Splash's) |
| 舞萌DX 2023 | 23000 | FESTiVAL (+PLUS) | 2023-06-08 | 100% |
| 舞萌DX 2024 | 24000 | BUDDiES (+PLUS) | 2024-06-06 | 99.9% |
| 舞萌DX 2025 | 25000 | PRiSM | 2025-06-11 | 100% |
| **舞萌DX 2026** (current) | 25500 | **PRiSM PLUS** | 2026-06-10 | 99.9% |

\* Release date of the earliest chart LXNS lists for that version, a close stand-in for the launch date.

| JP version | Launch | | JP version | Launch |
|---|---|---|---|---|
| BUDDiES | 2023-09-14 | | CiRCLE | 2025-09-18 |
| BUDDiES PLUS | 2024-03-21 | | CiRCLE PLUS | 2026-03-19 |
| PRiSM | 2024-09-12 | | **MAGiCAL** (current) | 2026-09-17 |
| PRiSM PLUS | 2025-03-13 | | | |

The mapping comes from Yuri-YuzuChaN/maimaiDX (`constants.DX_CN_VERSION`) and Diving-Fish's `from` labels.
`update_data.py` recomputes the "constants equal" share on every run.

**An inference for planning ahead (not confirmed):** if the next CN version runs on CiRCLE, two things change:

- B15 will count the new version and 舞萌DX 2026;
- AP will add 1.

Every CN version so far has taken over the constants of its JP version almost unchanged. So JP's CiRCLE constants
(`history["CiRCLE"]` in `data/jp/charts.json`) are a good forecast for the next CN version.

## 4. Data sources

| Use | Source | What it gives |
|---|---|---|
| JP charts, current and per-version constants | [DXRating](https://github.com/gekichumai/dxrating): API `miruku.dxrating.net/api/v1/dxdata`, falling back to the repo's `packages/dxdata/snapshot.json` | Charts of every server, `serverIds`, constants by version (`multiverInternalLevelValue`, from でらっくす PLUS on). Free to use; credit: "Data from DXRating (dxrating.net)" |
| CN charts, current and per-version constants | [LXNS](https://maimai.lxns.net): `GET /api/v0/maimai/song/list[?version=N]` | The current list with each chart's version code and release date; with `version`, the constants as of that CN version |
| CN cross-check, fitted difficulty | [Diving-Fish](https://github.com/Diving-Fish/maimaidx-prober): `music_data`, `chart_stats` | `ds` / `is_new` to cross-check LXNS (no constant differences on the charts both have); `fit_diff`, a difficulty fitted from Diving-Fish players' scores |
| Rule cross-check | [mai-tools](https://github.com/myjian/mai-tools) | Factor table, AP bonus, B15 rule. It also has JP per-version constant snapshots from UNiVERSE PLUS on, keyed by title; they are not merged here |

### What the constant history means

- **JP `history`**: only the values DXRating records explicitly, plus the current constant. Coverage for CiRCLE:
  about 93% of charts at level 12.0 and above; almost nothing at 11 and below. DXRating's own rule, which
  `constant` follows too, is "a version's value if recorded, else the current value".
- **CN `history`**: LXNS's constants for each CN version (`?version=`), plus the current constant. That is one
  snapshot per major version, so adjustments within a version are not visible. Songs that have been removed are
  not in the current list and have no history.
- **Finer history**: the daily data workflow commits `data/` whenever a chart changes, so `git log -p data/` shows
  every change from the day the repository started. Further back, DXRating's own repository has the git history of
  `packages/dxdata/dxdata.json` (the older format): about 380 commits since 2024-06, nearly daily in 2026.

## 5. Known limitations

- **New charts**: constants of charts released in the last weeks may be community measurements that change later.
  The daily update picks the corrections up.
- **Upcoming charts**: LXNS lists CN charts a few days before they open. The page treats them as unplayable until
  their release date, unless you move the date at the top.
- **CN ↔ JP matching**: songs are matched by music id, then by title. A few CN-only or renamed songs have no JP
  counterpart.
- **Old JP charts**: charts below about level 11 have no constant history. They never reach a B50 at the levels
  where planning matters.
- **Recomputed vs. in-game rating**: a rating recomputed from community constants can differ from the in-game one
  by a few points. Two causes: a chart's in-game constant differs from the community value, or a score is missing
  from the prober. The second happens, for example, on a song locked on the account, since locked songs are absent
  from the score pages. Add such scores to `data/player/manual.json`.
