# Planning

There are two ways to plan:

- **The web page** (`web/index.html`): you compose the plan by hand. See the README.
- **`plan.py`**: picks charts automatically by an estimated chance of success. It is described here.

```sh
python3 plan.py 16000                       # CN rules; newest saved import + data/player/manual.json
python3 plan.py 16000 --source lxns         # a specific import
python3 plan.py 16000 --alternatives 20     # list more alternatives
```

## Output

1. **Current state**: rating, B15 / B35 sums and their floors (the rating of the 15th / 35th chart).
2. **Your level**: for a few fitted difficulties, the share of your played charts there that reached SS+, SSS and
   SSS+.
3. **The plan**: one chart per line until the target is reached, with these columns:
   - target: the rank line to reach;
   - single: the chart's rating before → after;
   - +: the B50 total's real change, net of the chart it pushes out of its frame;
   - total: the running B50 total.
4. **Alternatives**: the best of the remaining candidates, to swap in for a chart you would rather not play.

## Method

**Candidates.** Released charts only (`release_date` ≤ today). For each chart, every rank line above its current
score counts as a candidate: S 97, S+ 98, SS 99, SS+ 99.5, SSS 100 and SSS+ 100.5. It must raise the B50 total.

- **Chart already in its frame**: the gain is new rating − old rating.
- **Chart not in its frame**: the gain is new rating − the frame's floor. If the frame is not full, the gain is the
  new rating.

Gains inside a rank (say 100.1 → 100.4) are worth 1–2 points and are not listed separately.

**Difficulty.** Diving-Fish's fitted difficulty (`fit_diff`) when it rests on at least 50 plays, otherwise the
constant.

**Chance (把握).** Estimated from your own scores only, in four steps:

1. **Rate per difficulty.** For each rank line, fit the share of your played charts that reached it, as a
   function of difficulty. The fit is a non-increasing isotonic regression, because a player's rate typically holds
   steady and then drops off a cliff. Only charts at or above the easiest B50 constant − 0.5 are used: easier
   charts are mostly played casually and would bend the low end of the curve.
2. **Condition on the line already held.** For a chart you have played, divide by the rate of the line it already
   holds. For example, if 23% of your charts near fitted 14.0 are SSS+ and 72% are SSS, a chart already at SSS
   reaches SSS+ with chance 23% / 72% ≈ 32%.
3. **Closeness bonus.** The band below a line is 0.5% wide for SS+ and above, 1% below that. The closer the current
   score is to the line inside that band, the higher the chance: 100.47% towards SSS+ comes out near 95%.
4. **Clamp.** Chances are limited to 3%–97%.

**Choice.** At each step, take the candidate with the highest gain ÷ (−ln chance). −ln chance is a difficulty cost:
90% costs 0.11 and 50% costs 0.69. After each pick, B15 / B35 and their floors are recomputed, until the target
is reached. Picking this way approximately maximizes the chance that the whole plan succeeds. A chart appears in
the plan at most once.

## Limitations

- **The chance is a rough estimate.** It comes from the distribution of your best scores and ignores practice time,
  chart style and technique. Use it to compare charts, not as a probability.
- **Unplayed charts may still be locked.** The plan says how many of its charts you have not played.
- **Current version only.** Planning for a future version (say the next CN one) would need a forecast of its new
  charts and constants.
- **China server only.** The imports come from CN probers. Supporting JP would need JP score import, and the AP +1 as
  a candidate target.
