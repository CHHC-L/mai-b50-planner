# mai-b50-planner

A planner for maimai DX rating. Import your scores, set a target rating, and work out which charts to push
and how far. It targets the China server (舞萌DX) and follows each server's own rules and version progress.
Chart constants for the Japanese server are kept too.

- **Web page**: `web/`, a static site. You compose a plan by hand, and the page shows how many charts of each
  constant and rank you would need.
- **Command-line tools**: chart data, rating maths, score import and an automatic planner.

## The web page

Live at **https://chhc-l.github.io/mai-b50-planner/** once Pages is enabled (see [Deploying](#deploying-to-github-pages)).

1. **Import your scores.** Click **从落雪导入** (LXNS) or **从水鱼导入** (Diving-Fish) at the top right and paste a token:
   - **LXNS**: a read-only API key from [maimai.lxns.net → 账号详情](https://maimai.lxns.net/user/profile).
   - **Diving-Fish**: the *Import-Token* from the [prober](https://www.diving-fish.com/maimaidx/prober/) under
     *编辑个人资料*.
2. **Set a target.** Click the target number (right of the arrows) and type a rating.
3. **Read the grid.** For each frame (B15 new charts, B35 old charts), each constant (rows) and rank (columns),
   a cell shows how many charts of that kind you would have to push to reach the target.
   - Next to the count are the points they add and the single-chart rating.
   - Grey `+n` cells cannot close the gap alone.
   - Once the plan reaches the target, the grid shows what one more chart of each kind would add instead.
4. **Pick charts.** Click a cell to list its charts below, or filter the list yourself.
   - Tick a row to add it to the plan, and change its target in the row's dropdown.
   - Rows stay where they are while you edit them. The list re-sorts only when you change a filter or click a cell.
5. **The plan** (right) lists each chart with what it adds: the B50 total minus the total without it. Export it as text.

The date at the top decides which charts count as playable. Upcoming releases appear as a button (for example
*11月更新后*), so you can plan for them before they open.

### Privacy

- **Scores stay in your browser.** The page requests your scores directly from LXNS or Diving-Fish, which both allow
  cross-origin requests. The scores, and your plan, are kept in the browser's `localStorage`. Nothing is sent
  anywhere else.
- **Tokens are not saved unless you tick 在这个浏览器里记住.** Even then they are only kept in `localStorage`. On
  GitHub Pages, `localStorage` is shared by every page under the same `<user>.github.io` origin, so other Pages
  sites of the same account could read it.

## Rating rules in brief

Full details, with sources: [docs/rating.md](docs/rating.md).

- **Single chart**: `floor(constant × factor(achievement) × min(achievement, 100.5) / 100)`. The factor table is
  shared by DXRating, Diving-Fish and mai-tools.
- **Total**: rating = best 15 charts of the new versions (B15) + best 35 of the rest (B35).
- **Up to PRiSM PLUS**: B15 counts the current version only.
- **From CiRCLE (JP, 2025-09)**: B15 counts the current version and the previous one, and an AP or AP+ adds 1 to
  a chart's rating.
- **China server now**: 舞萌DX 2026 runs on PRiSM PLUS, so B15 is 舞萌DX 2026 only and AP adds nothing.

## Data

| Source | Used for |
|---|---|
| [DXRating](https://dxrating.net) ([repo](https://github.com/gekichumai/dxrating)) | JP charts, current and per-version constants |
| [LXNS (落雪查分器)](https://maimai.lxns.net) | CN charts, constants, per-version constants, release dates |
| [Diving-Fish (水鱼查分器)](https://www.diving-fish.com/maimaidx/prober/) ([repo](https://github.com/Diving-Fish/maimaidx-prober)) | cross-check of CN constants; fitted difficulty (拟合定数) |

Data from DXRating (dxrating.net). Chart constants and statistics come from the LXNS and Diving-Fish
communities. Song titles, charts and other game content belong to SEGA and their rights holders.

`scripts/update_data.py` downloads the sources into `data/raw/`, which is not committed. It then rebuilds:

- `data/cn/charts.json` and `data/jp/charts.json`: one chart per line, with current constant, version, release
  date, whether it counts as new, constants by version, and (CN) Diving-Fish's fitted difficulty.
- `data/versions.json`: the current version and rating rule of each server, and the CN ↔ JP version mapping.
- `web/data/charts-cn.json`: the compact chart list the web page loads.

### Automatic updates

`.github/workflows/update-data.yml` runs every day at 03:37 China time, and on demand from the Actions tab. It
commits the rebuilt files whenever any chart changed, so the git history of `data/` doubles as a history of
constant changes. When it commits, it also redeploys the page. A version must be listed in
`scripts/update_data.py` for its rules to be applied:

- a new JP version goes in `JP_VERSIONS`;
- a new CN version goes in `CN_JP_BASIS`, together with the JP version it runs on.

When an unknown version shows up, the workflow fails and GitHub emails you. GitHub turns off scheduled workflows
after 60 days without activity in the repository; re-enable it from the Actions tab if that happens.

## Deploying to GitHub Pages

The site is the `web/` folder. `.github/workflows/pages.yml` publishes it.

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. **Settings → Secrets and variables → Actions → Variables → New repository variable**: name `PAGES_ENABLED`,
   value `true`. Until this is set, the deploy job is skipped instead of failing.
3. **Actions → Deploy Pages → Run workflow.**

After that, the page redeploys on every push that changes `web/`, and after every data update that changed a chart.

## Local use

Python 3.9+ with no third-party packages.

```sh
python3 scripts/update_data.py            # download the sources and rebuild data/ and web/data/
python3 scripts/update_data.py --offline  # rebuild from data/raw/ only
python3 rating.py                         # self-check of the rating maths

python3 serve.py                          # the web page at http://127.0.0.1:8765
```

Opened through `serve.py`, the page does three extra things:

- If the browser has no scores yet, it reads the newest import saved by `scores.py`.
- It merges `data/player/manual.json`.
- It also writes the plan to `data/player/plan.json`.

The server listens on 127.0.0.1 only and accepts writes only as JSON from that host.

### Command-line import and planning

```sh
python3 scores.py lxns                        # all scores, with the LXNS personal API key
python3 scores.py divingfish                  # all scores, with the Diving-Fish Import-Token
python3 scores.py divingfish --username NAME  # public B50 only, no token
python3 scores.py show data/player/lxns.json  # re-check a saved import
python3 plan.py 16000                         # an automatic plan towards 16000 (see docs/planning.md)
```

The commands look for tokens in this order: the command-line flag, then the `LXNS_TOKEN` / `DF_IMPORT_TOKEN`
environment variables, then `secrets.json`:

```json
{ "lxns_token": "…", "df_import_token": "…" }
```

`secrets.json` and `data/player/` are git-ignored.

**Scores the probers cannot see** go in `data/player/manual.json`. For example, a song locked on your account is
missing from the score pages. Entries look like this:

```json
[{ "title": "Song title", "type": "dx", "difficulty": "master", "achievement": 100.6 }]
```

`type` is `dx` or `std`, and `combo` is optional (`fc`, `fcp`, `ap` or `app`). `music_id` can replace `title`.
Per chart, the higher achievement wins.

### Uploading scores to Diving-Fish from WeChat (macOS)

`tools/prober-proxy/run.sh` starts Diving-Fish's official proxy updater: download
`maimaidx-prober-proxy-darwin-arm64-<version>` from the
[Diving-Fish releases](https://github.com/Diving-Fish/maimaidx-prober/releases) into that folder.

- **First run**: the updater installs a local root certificate into your login keychain and asks you to authorize
  your Diving-Fish account in the browser. It then decrypts only `maimai.wahlap.com` and `chunithm.wahlap.com`.
- **Upload**: open 舞萌 | 中二 → 我的记录 → 舞萌DX in desktop WeChat.
- **Proxy settings**: the updater points the Wi-Fi proxy at `127.0.0.1:8033`. On exit `run.sh` restores the previous
  Wi-Fi proxy settings, which the updater alone would just switch off.

Remove the certificate when you no longer need it:

```sh
tools/prober-proxy/maimaidx-prober-proxy-darwin-arm64-<version> -uninstall-cert
```

## Layout

```
web/index.html            the web page (static)
web/data/charts-cn.json   chart list for the page (generated)
data/{cn,jp}/charts.json  chart lists with constants by version (generated)
data/versions.json        current versions and rating rules (generated)
scripts/update_data.py    download sources, rebuild data/ and web/data/
rating.py                 single-chart rating, Best 50, lowest achievement for a rating
scores.py                 import scores from LXNS / Diving-Fish (command line)
plan.py                   automatic planner (command line)
serve.py                  serve the page locally, with data/player/ sync
docs/rating.md            rating rules, version history, data sources
docs/planning.md          how plan.py chooses charts
```
