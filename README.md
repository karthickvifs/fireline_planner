# Fireline Planner (QGIS Plugin)

Three chained Processing algorithms to prioritize forest blocks for firebreak
construction and generate candidate fire-line alignments.

**Full user manual (PDF, with diagrams):** see `docs/Fireline_Planner_User_Manual.pdf`
in this folder — covers objective, data collection, CRS requirements, installation,
step-by-step usage, interpreting results, and troubleshooting.

## Install

1. Copy the `fireline_planner` folder into your QGIS plugins directory:
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - Mac: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
2. Restart QGIS, open **Plugin Manager**, enable "Fireline Planner".
3. Find the three tools in the **Processing Toolbox** under "Fireline Planner".

## IMPORTANT: before you run anything

- **All layers must share the same projected CRS in metres** (e.g. a UTM zone).
  If your data is in lat/long (EPSG:4326), reproject everything first
  (`Vector > Data Management Tools > Reproject Layer`). Distance and slope
  calculations will be wrong otherwise.
- The DEM should cover the full extent of your forest blocks.

## Workflow

Run these three tools in order (chain them manually, or build a Processing
Model in Model Builder to run all three in one click):

### 1. Score Forest Block Vulnerability
Inputs: forest blocks, fire points, villages, roads, HQ points, DEM, and five
weights (fire history, slope, village proximity, road distance, HQ distance —
these don't need to sum to 1, they're normalized automatically).
Output: forest blocks + a `priority_score` field (0–1) plus the raw and
normalized values for each factor, so you can audit the scoring.

### 2. Prioritize Blocks & Allocate Fire Line Budget
Inputs: the scored blocks from step 1, villages, your total fire-line budget
in km (e.g. 500), and the "village interface" distance (how close to a
village counts as an interface — default 300 m).
Output: blocks ranked by `rank`, with `allocated_len_m` / `allocated_km`
showing how much fire line each block gets, starting from the highest
priority block down, until the budget runs out.

### 3. Generate Fire Line Placement
Inputs: the allocated blocks from step 2, villages, the same interface
distance, and a "set-back" distance (how far inside the forest edge the line
should sit — default 30 m, so it isn't literally on the property boundary).
Output: an actual line layer — the exact alignment, cut to length, for every
funded block. This is what you'd hand to a field team.

## Tuning notes

- If step 3 skips blocks with "no forest-village interface", increase the
  interface distance in step 2/3, or check that villages actually sit near
  those blocks.
- If a block's true buildable boundary is shorter than the interface length
  detected, adjust the set-back distance or interface distance.
- The prioritization is a weighted heuristic, not a true optimizer — it's
  meant to give a strong, explainable first-pass plan you can review and
  adjust, not an unquestionable answer. Field verification is essential
  before construction.
