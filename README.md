## Unified Project → DOE/Cell → Cycler Performance workflow

Open `/` and **choose a project first**. Its workflow then shows DOE Register,
design categories, Batch/Cell Registry, Test/Channel Registry, Performance and
Issues. Performance **contains the actual 3D cycler**, live SOH and experimental
ML charts, scoped to the selected project's channels. It does not link out to a
separate demo dataset. Selecting a DOE in the workflow or cell inside 3D keeps
the same DOE/channel selected.

The demo now uses **six replicate cells per DOE**:
- `DOE-P-LFP01`: PRISMATIC LFP01, C01–C06 on CH01–06.
- `DOE-C-LFP01`: CYLINDRICAL LFP01, C01–C06 on CH07–12.

Each DOE has one shared original BOM/revision and batch, with six unique cell
and test IDs. Performance/3D selection distinguishes replicates by C01–C06.
The home summary aggregates running count and mean/min/max SOH per DOE. Each
cell's telemetry and experimental ML remain independent. Editing the shared
recipe is blocked if any of its six cells already has telemetry. This supersedes
the previous one-DOE-per-cell mapping; old local records are preserved.
SIB projects remain empty because no sodium channels are assigned.

`GET /api/project-workflow?project=<project-id>` returns a consistent locked
snapshot of live telemetry, persisted original DOE definitions and linked
batch/cell/test records, SOH/ML histories, alarms and project issues.
`/api/live-report` uses the same mapping (optionally filtered by project).
Original DOE recipes persist in SQLite without reseeding duplicates. Faults
create persisted issues linked to the exact session/test/cell/DOE, with Owner,
Due Date and resolution. Resolving an issue never clears a safety STOP.
Historical issues retain their session IDs when the cycler is reset.

Use **Nhập / sửa thiết kế DOE** in the DOE tab to edit the same DOE's 60-field
BOM, Owner and Objective before testing begins. Saving creates a new revision
and preserves the previous revision in SQLite. Editing is rejected while the
rack runs or that channel has telemetry; export and Reset before preparing the
next test. Metadata changes do not recalibrate the generic simulation physics.

Performance CSV/JSON export only the selected project's channels, with original
BOM, DOE/cell name, revision, batch, channel, session/time, telemetry, ML provenance
and issues. JSON also includes histories. No separate demo seed is required.
A legacy all-channel page at `/index.html` preserves every old feature; it can
also be filtered by `?project=prismatic-lfp01&doe=DOE-P-LFP01&channel=3`.

Start/Pause/Reset inside the embedded cycler apply to the **whole rack**, even
when the display is project-filtered. Reset creates a new runtime session and
clears in-memory telemetry/history; export first. Persisted DOE information and
issues survive. The model remains generic 3.0–4.2 V, not calibrated LFP/SIB;
NASA ML is experimental. Usable Ah/resistance are model outputs, not full-cycle
discharge capacity or pulse-measured DCIR. CE/final target assessment stay pending.

Examples: `results/unified-project-workflow.png`, `unified-performance-3d.png`,
`unified-project-performance.csv`, `unified-project-report.json`.

## Legacy manual lifecycle API and historical demo artifacts

The manual lifecycle API and the earlier static demo seed remain available
for compatibility. They do not populate the current live Project Workflow.
Existing local records are preserved; `results/lifecycle-*` are historical examples.

Click **Tạo data demo** or run `python -B seed_demo.py` before starting the server.
This idempotently adds 4 projects × 2 DOE records (V01) × 3 cells = 24 demo cells,
8 batches, 24 tests and 8 critical issues. Existing records are preserved.
Demo running statuses are scenario snapshots; they do not claim a connected
instrument or continuously advancing telemetry. All demo data is tagged `demo`.

The registry supports immutable DOE code/revision, Objective, Owner and all
60 original BOM fields, batch-to-revision links, cell identity, test equipment,
channel, protocol, cycle summaries and issue Owner/Due Date/resolution.
Create records in that order through the navigation tabs. On DOE creation,
copy a saved sheet from the original design workspace or edit the full BOM JSON.
New revisions are new immutable records; existing batches retain the old revision.
No automatic manufacturing runs are created from these design inputs.

Manual tests accept incremental cycle-summary JSON using **Thêm cycles**.
Cycle indices must increase; duplicate/out-of-order rows roll back the import.
Temperature ≥45°C sets registry STOP and creates a critical issue. Closed tests
reject further cycles; retest creates a new test. This **does not send a STOP
command to equipment**; a device adapter is still required. Running equipment/
channel occupancy conflicts are rejected. Manual and demo chains cannot mix.
Manual cycle imports are distinct from live cycler telemetry; the current Project
Workflow uses the cycler directly, rather than these manual snapshots.

Performance shows capacity, design-normalized SOH, first-cycle retention, entered
DCIR, CE and temperature, plus a SOH curve and per-DOE summaries. Pass checks
only minimum capacity and temperature <45°C, not all design targets. Comparing
unequal cycle horizons is descriptive, not a causal DOE effect estimate.
Demo LFP tests run the existing NASA RF on explicitly synthetic illustrative
features; the stored features and model ID are exported, and outputs are marked
experimental and invalid for hardware control. There is no calibrated project
model. SIB and manual tests show unavailable ML instead of invented predictions.

Management CSV includes project/DOE revision/objective/owner, batch/cell/test,
equipment/channel/protocol, data source, STOP/issue context, performance,
experimental ML provenance, and all 60 immutable original design fields under
`reference_bom.*`. JSON adds all cycle histories and linked records. These are
cycle summaries, not raw time-series measurements. SQLite remains local and
ignored by Git; committed `results/lifecycle-*` files are synthetic examples.

# Digital-Twin Battery Cell

Battery cycler simulator with a realtime 12-cell 3D dashboard.

Requires Python 3.11+; no external dependencies.

## Project → cell design sheet → DOE → performance / issues

The server's root page now opens the **project workspace**. Choose one of:

- PRISMATIC · LFP01
- PRISMATIC · SIB
- CYLINDRICAL · LFP01
- CYLINDRICAL · SIB

Capacity fields support 0.1–2,000 Ah for nominal scale, including large
prismatic designs; accepting a value does not establish model validity at that scale.

SIB means sodium-ion. The example model currently supports NFPP cathode,
HardCarbon anode and sodium electrolyte profiles; these are illustrative
assumptions, not production specifications. LFP01 uses a generic LFP profile,
not a manufacturer-grade characterization. Form factor is tracked for project
identity and comparison but does not automatically create a calibrated
prismatic/cylindrical geometry model.

Create a named design/DOE sheet with **60 fields** grouped as Cell, Cathode,
Anode, Assembly and Formation. The sheet covers N/P, areal capacity, nominal
voltage, typical/minimum 0.33C capacity, 1C capacity, weight and Wh/kg targets;
material identities and dry wt% for all requested active materials, binders,
conductors, additive and dispersant; solvent, foils, foil/coating thickness,
loading and density; layer counts, separator, JR thickness, packing ratio,
electrolyte and amount, CAN/CAP and mass, and formation protocol. Cathode and
anode dry totals are computed separately, excluding solvent. Optional unused
components use 0%, not an invented material.

Every field is labeled **modeled**, **target**, **consistency validation** or
**recorded only**. Recorded-only fields, including formulation component
identities beyond the supported active-material profile, foil/assembly details
and formation protocol, do not silently change performance. Unknown active
profiles or unsupported active-material blends can be saved for traceability
but block simulation. Composition totals, required targets, thickness/loading/
density consistency, N/P consistency and project chemistry are checked.

Use **Save → Configure and run DOE**. The project-specific DOE screen starts
from the saved sheet, restricts material families, and executes bounded DOE
samples in background workers. Return to **Performance / Issues** to select
up to four experiments and compare energy, final SOH, counts and target pass.
Different cycle horizons are explicitly flagged. Each generated run/replicate
represents one simulated cell sample, not a physical cycler channel.

An experiment captures an immutable sheet revision. DOE overrides are recorded
in the report and expanded into each run's `effective_bom`: cathode inactive
fractions are rescaled when active fraction changes; modeled density/loading
and N/P-related anode loading/thickness are derived consistently. Original
reference sheets remain unchanged. Exported per-cell CSV includes project,
chemistry, form factor, worksheet revision, sample/design IDs, grouped ML split,
project/experiment names, all 60 original design inputs (`reference_bom.*`),
all effective trial fields (`bom.*`), status and performance. The original inputs
are the immutable design supplied by the team, kept beside results for management
review; trial overrides never replace these reference columns. JSON retains the reference
sheet, overrides, curves and model assumptions. Synthetic data stays tagged.
If exported before an experiment report completes, `bom_basis=reference_sheet_pending`
marks reference-only recipe fields; completed reports use `effective_trial`.

**Pass means all configured targets pass**, not just Wh/kg: initial specific
energy ≥ target; modeled 0.33C capacity ≥ minimum; modeled 1C capacity ≥ target;
modeled mass ≤ weight limit; nominal voltage within 5% of its target. Target
capacities are explicit reference targets, not measured capacities. A cell
can complete successfully but miss targets; this is distinct from STOP or an
infeasible design. The additional rate-capacity outputs are illustrative
responses from the transport model, not separate measured charge/discharge tests.

KPI counts apply to selected DOE experiments. The running count comes from
actual worker/sample state and can return to zero quickly for small studies;
it is not a fabricated count or the number of physical cycler channels.
Issue count covers the whole project. Issues are generated from sheet
validation, failed targets, infeasible samples, thermal stops or interrupted
execution. Resolving an issue requires a note and preserves the original
cell failure. Editing a sheet revalidates its issues. The independent 12-channel
3D demo remains available at `/index.html` and is not assigned to projects.

Workspace state persists in **`data/workspace.sqlite3`**, ignored by Git.
Reloading or restarting the server preserves sheets, revisions, experiments,
results and resolutions. Up to two experiments execute concurrently, with a
maximum 100 experiments per project. Stale unfinished work is marked interrupted
after 120 seconds without a worker heartbeat; it is not silently counted as
running forever. To back up the full workspace, stop the server and copy the
SQLite file. Updating code does not replace this database. Demo screenshots
and exported example data in `results/` were produced using a separate temporary
database; a new user's workspace starts empty.

Endpoints use `/api/workspace/`: `schema`, `dashboard?project=<id>`,
`designs/<id>` (GET context), `designs` (POST save with revision),
`experiments` (POST start), `experiments/<id>` (GET status/report) and
`issues/<id>/resolve` (POST note). The dashboard accepts an optional comma-separated
`experiments` filter (up to four from the same project). Same-origin checks and
bounded request bodies apply. Material/model coefficients remain uncalibrated;
no physical cycler or electrochemical formation controller is connected.

```sh
python -B server.py --port 8000
python -B -m unittest -v test_workspace test_doe test_live_features test_integrations test_aging
```

[Project workflow screenshots and executed validation](results/PROJECT-WORKSPACE-REPORT.md).

## DOE · Cell Design Performance

Choose **DOE · Cell Design** on the dashboard, or open `/doe.html` on the
same server. DOE runs independently and does not change the 12 cycler channels.

**Energy Density Target means cell-level specific energy in Wh/kg.** It is
a fixed objective, not a causal input that forces modeled energy to increase.
Each run reports initial and final Wh/kg, target margin and initial-target
pass/fail. Cathode bulk density (g/cm³) is a separate physical design input.

Select 2–4 levels for Capacity Target (nominal Ah), N/P ratio, cathode
(LFP/NMC622/NMC811), anode (Graphite/Si-Graphite/LTO), example electrolyte,
cathode bulk density, dry coating loading, active fraction, anode porosity,
effective electrode conductivity, electrolyte g/Ah, temperature and C-rate.
Unselected factors stay fixed. Cathode porosity and thickness are derived
from density, solid-mixture composition and loading to avoid inconsistent
independent parameters. Loading is dry coating mass per single coated face.

Methods: full factorial, one factor at a time (OFAT), and balanced-level
random candidates with duplicate removal. Retained random samples need not
remain orthogonal or perfectly balanced. Preview the matrix before running.
Limits: 256 runs, 5,000 cycles/run, 1–5 replicates. The seed reproduces order
and optional synthetic manufacturing variation. At variation=0, repetitions
are identical and do not supply independent statistical evidence.

Select a metric to inspect marginal level means and effect ranges; compare
the energy/SOH trade-off and click a row for its SOH curve and derived
geometry. These descriptive effects depend on chosen ranges/interactions;
they are not causal effects or significance tests. Infeasible designs and
thermal stops remain in results with reasons and are excluded from completed
comparisons, which may unbalance factors. Unobserved 80% SOH crossings stay
null with `eol_censored=true`, not an invented zero-cycle life.

**Model limits:** material capacities, voltages, resistance/transport terms,
thermal and aging multipliers are illustrative assumptions, not fitted cell
measurements. JSON includes all material constants. Responses use mass/area
balance, approximate electrode transport, steady operating temperature and
cycle-level exponential fade. No detailed voltage simulation, plating model,
general electrolyte compatibility assessment or safety qualification is
provided. The NMC/ether rejection is a demonstration constraint. NASA ML is
not used to extrapolate material design changes.

CSV contains tabular inputs/responses; JSON adds configuration, units,
material assumptions, curves and analyses. All records retain
`data_origin=synthetic_doe`, `calibrated=false`, model version, seed,
design_id, replicate, run order, status and design-grouped `ml_split`.
Replicates of a physical design stay in the same split across seeds and
energy-target changes. Small studies may not populate all splits; verify
coverage before training. Use completed runs for performance regression,
handle EOL censoring, and keep synthetic and measured data separate. This
prepares future optimization; it does not implement a validated ML optimizer.

```sh
python -B run_doe.py --output doe-output
python -B run_doe.py --config results/doe-example.json --output doe-output
python -B -m unittest -v test_doe
```

APIs: `GET /api/doe/schema`, `POST /api/doe/plan`, `POST /api/doe/run`.
POST accepts `method`, `baseline`, `vary`, `cycles`, `replicates`, `seed`,
`samples`, `variation_percent`. Numeric/material validation, same-origin
checks, 64 KiB request and run-count limits apply. No extra packages needed.

[Executed DOE report and screenshot](results/DOE-REPORT.md).

## BatteryLake metadata + trained ML on real discharge records

### Live per-channel ML RUL

The 12 simulated channels now feed their running voltage/current/temperature
into independent early-discharge windows. Each channel waits for a complete
600-second discharge window (at least 10 samples), computes the same
seven features as the NASA training pipeline, and performs server-side
Random Forest inference once per discharge cycle. The latest result,
feature cycle, sample count and simulated update timestamp are included
in `/api/state` under each channel's `live_ml` field and shown in the
channel table and selected-cell charts. The SOH chart plots simulated SOH
against ML SOH on a simulated-time axis, with an 80% EOL reference. The
simulated curve is visible from startup and receives a point every 30
simulated seconds, including charge/rest. ML points are added only after
each complete early-discharge window; no ML values are invented while
waiting. The second chart plots predicted
remaining cycles. Each point is one completed feature window, not a
fabricated intermediate prediction. Up to 200 per-channel points are held
in the server under `live_ml_history`, so browser refresh does not lose the
server's window. Pause freezes collection; Reset clears all predictions.

**These live results are experimental:** NASA-trained trees have not been
calibrated or validated on the synthetic rack signals. The NASA hold-out
metrics do not describe accuracy on these channels. They are not the
physics scenario forecast and must not be interpreted as verified battery
life. The replay remains a separate validated NASA backtest. Live RUL
means additional cycles to 80% SOH, not remaining steps in the three-cycle
demo. Predictions may fluctuate; they are not forced to decrease.

No physical cycler adapter is connected. Real channel updates require the
instrument's protocol/API or CSV stream and a model validated for its cells
and test conditions. Never feed charge/rest samples into this discharge
model. Features exclude current-cycle capacity and future data; invalid or
out-of-order timestamps are rejected. Short discharges show insufficient
data instead of inventing a prediction. The independent safety checks run
before feature collection; a STOP freezes predictions and current.

See [executed live-channel results](results/LIVE-ML-REPORT.md).

The new **BatteryLake** panel calls the public metadata JSON interface from
`tianwen1209/batterylake`, pinned at commit
`8d2a7304e4841b815287d3d0b2fcc67fea95b200`. You can search/filter its
40 datasets, inspect a record, and copy a temperature setpoint and the
maximum discharge C-rate into the illustrative scenario forecast.
Metadata does not itself contain capacity trajectories or calibrate a model.
Use the original links for data access, licensing and citation. The catalog
requires Internet access to `raw.githubusercontent.com`; errors are reported
without replacing the catalog with synthetic records.

Local read-only APIs:

```text
GET /api/batterylake/datasets?chemistry=LCO&task=SOH&search=NASA
GET /api/batterylake/datasets/dataset_01
GET /api/ml/replay
POST /api/ml/predict
```

BatteryLake's website API console contains simulated `/v1` calls. This
integration uses their actual public metadata files rather than claiming
an authenticated REST model service is connected.

The **ML Prediction / Raw Data Replay** panel uses Random Forest models
trained on NASA discharge time-series CSV records (a public export linked
to the NASA dataset represented by BatteryLake `dataset_01`). No simulated
cycler data is used to train these models. B0005/B0006/B0007 are training
cells; B0018 is a separate test cell. Predictions use cycle number and
voltage/current/temperature from the first 600 discharge seconds. Capacity
from the current full discharge is excluded from the features.

Load the replay, press Play, or move its cycle slider. The browser calls
`POST /api/ml/predict` for actual model inference. SOH compares measured
capacity / first observed capacity against predicted SOH; RUL compares
remaining cycles to the first observed 80% crossing against prediction.
Ground truth RUL is retrospective and is never a model input. RUL metrics
exclude post-EOL rows; the replay retains them and may show nonzero model
RUL after the measured crossing. Do not apply these four-cell NASA models
to arbitrary chemistries or the illustrative 12-cell rack.

See [ML metrics, data provenance and screenshot](results/ML-REPORT.md).
The server reads our own exported JSON forests, without pickle/joblib or
runtime ML packages. **Optional retraining** needs:

```sh
python -m pip install -r requirements-ml.txt
python -B train_ml.py
python -B -m unittest -v test_aging test_integrations
```

Training downloads the pinned 21 MB measured CSV export, verifies SHA-256,
extracts 636 cycles from 169,766 samples, and overwrites our model/report
artifacts. The raw download is ignored under `data/`. No third-party model
file is loaded. `POST /api/ml/predict` accepts a JSON `features` object with
exactly `cycle`, `voltage_mean`, `voltage_std`, `voltage_end`,
`temperature_mean`, `current_mean` and `ambient_temperature` (V, A, °C).

Reports and JSON artifacts explicitly use UTF-8 on Windows as well as
Linux. The pinned retraining dependencies require Python 3.11 or later;
the Python 3.8 runtime is not supported by that requirements file.

## Abnormal-cell cases and STOP alarms

Choose a cell and inject overheat (50 °C), overvoltage (4.5 V), overcurrent
(8 A), or sudden capacity loss. Click Start if paused; injection takes
effect at the next simulation step. A violation immediately latches
**STOP**, pauses the entire rack, sets all channel currents to zero, and
records the offending values and reason. Start is rejected with HTTP 409
until Reset clears the fault and creates fresh cells.

The same limits apply to uninjected telemetry: 45 °C, voltage outside
3.0–4.2 V (1e-5 V discretization tolerance), |current| above 2.2 A, or SOH
below 80%. These limits match the demonstration protocol, not a universal
battery safety standard. The simulation source freezes on STOP; it is not
an independent hardware interlock and does not command a physical cycler.

See [executed abnormal-case report](results/SAFETY-REPORT.md).

## SOH, cycle prediction and battery degradation

The dashboard now tracks SOH, usable capacity, internal resistance and
equivalent full cycles (EFC) for every cell. Aging feeds back into subsequent
voltage, thermal and charge/discharge calculations. EFC is total charge plus
discharge throughput divided by twice the nominal capacity; it is different
from the protocol's numbered cycles. Reset creates fresh, unaged cells.

Select a cell and use **Cycle Prediction / Battery Degradation** to compare
temperature, C-rate, DoD, forecast horizon and EOL threshold. The forecast
starts from that cell's current simulated SOH/EFC, refreshes every five
seconds, and estimates additional operational cycles to EOL. Its scenario
does not change the realtime cycling protocol. CSV exports include scenario
metadata, SOH, capacity, resistance and sensitivity curves. Scenario edits
disable export until a new valid forecast is computed.

The model uses `SOH = exp(-damage)`, with damage per EFC equal to
`0.00025 * 2^((temperature-25)/10) * sqrt(max(C-rate,0.1)) * DoD^0.3`.
Live aging uses DoD=1 as its throughput-based approximation. Future
operational cycles add DoD EFC each. Capacity is nominal capacity times SOH;
resistance is initial resistance times `1 + 1.5*(1-SOH)`. These coefficients
are demonstration assumptions, not chemistry-specific fits or AI outputs.
The ±30% bands vary the aging rate; they are not confidence intervals.

[BatteryTwin Studio](https://batterytwin.ai/#studio) was requested as a
reference. This project does not use BatteryTwin code, data or API: its
website could not be read from this environment, and no API documentation
or credentials were supplied. A real integration still needs documented
endpoints, request/response formats and authentication. No API key belongs
in the browser or repository.

See [executed results and screenshots](results/REPORT.md). Reproduce the
12-cell, three-cycle report and baseline/warm/fast forecasts with:

```sh
python -B -m unittest -v test_aging
python -B report.py --output results
```

JSON predictions are served at `/api/prediction?cell=1&temperature_c=25&c_rate=1&dod=0.8&horizon=2000&eol_soh=0.8`.
Cell IDs are 1–12, temperature −10 to 60 °C, C-rate 0.1–5, DoD 0.05–1,
horizon 10–10,000 integer cycles and EOL SOH 0.5–0.95. Invalid, duplicate,
nonfinite or unknown parameters return HTTP 400.

## Dashboard screenshots and simulation results

![Battery cycler dashboard with ML replay](results/dashboard-ml.png)

[ML test results](results/ML-REPORT.md) · [Abnormal cell STOP cases](results/SAFETY-REPORT.md)

All 12 cells completed three cycles in the recorded example run. The highest
temperature was 28.72 °C, and the last cell finished after approximately
8.06 simulated hours. These are illustrative model outputs, not hardware
measurements. See the [completed dashboard](results/dashboard-aging-completed.png)
and [latest executed report](results/REPORT.md). The earlier `results.json`
and `dashboard-running.png` files retain the original run before aging was added.

## Realtime 3D dashboard

```sh
python -B server.py --port 8000
```

Open `/index.html` on port 8000 for the 3D rack, or use the project workspace
at `/` on the same machine. The server
binds to loopback by default. The cloud onboarding interface does not provide
a browser preview; local requests can still validate the server.

The dashboard displays a 12-channel rack using WebGL 2 and bundled Three.js
0.180.0 (MIT license in `web/vendor/THREE-LICENSE.txt`). No CDN, npm install,
or runtime Internet connection is needed. Drag to rotate, scroll to zoom,
and select a cell in 3D, the dropdown, or the channel table.

Start/pause/reset control the shared simulation. Speed options 1×, 10×, 60×,
and 300× mean simulated seconds per wall-clock second. Telemetry is polled
every 250 ms and charts retain up to 240 samples per cell. Reset clears
history. Charts show temperature, voltage, current and SOC versus simulated
time, with independent automatically scaled vertical ranges.

All cells perform three cycles at 2 A, with slightly different capacities,
resistances, initial SOCs and ambient temperatures. The fixed temperature
color scale is 20–45 °C and is clamped outside that range. Colors indicate
one uniform modeled temperature per cell, not a spatial temperature field.
Each cell stops independently on completion or a thermal fault. The server
uses the Python model in `main.py`; its simulation progresses even if the
browser is closed. Pause freezes simulation time. The server is a local
development tool with shared state, without user authentication.

## Run on Replit

1. Create a Python app in Replit and upload/extract the supplied
   `cycler-replit.zip` into the project root. Ensure `server.py`, `main.py`,
   `.replit`, and the complete `web/` directory are at the root, not inside
   an extra enclosing folder. Preserve other files if importing into an
   existing project. Alternatively import the GitHub repository after
   these files are available on the repository's `main` branch.
2. The supplied `.replit` uses Python 3.11 and sets the Run command to
   `python -B server.py --host 0.0.0.0 --port 8000`.
   If configuring an existing app manually, use this command and expose
   internal port 8000 as external port 80 in its port configuration.
3. Click Run and open the app's Preview/Webview. Select a project, or choose
   **Cycler 3D** then **Bắt đầu** for the independent rack simulation.
   Replit's preview forwards browser requests to the Python
   server; no additional packages or API keys are required.
4. If your runtime supplies a different `PORT`, use
   `python -B server.py --host 0.0.0.0` to read it automatically and configure
   port forwarding accordingly. An explicit `--port` takes priority.

The app accepts same-host HTTP and HTTPS browser origins so controls work
behind the HTTPS preview proxy. Keep your demo's access limited to intended
viewers: simulation controls are shared across all visitors. Run/Preview is
for development; public publishing and hosting costs are separate Replit
actions. Browser WebGL 2 support is required for 3D. Reset or restarting
the server clears the simulation, and no telemetry is saved persistently.

## CSV simulation

```sh
python main.py --cycles 2 --capacity-ah 2.5 --current-a 1 --output /tmp/cycler.csv
```

Each cycle charges at constant current, tapers at 4.2 V, rests, discharges
at constant current to 3.0 V, and rests again. Positive current charges;
negative current discharges. CSV measurements describe the end of each step.
Charge ends when the CV current falls to 5% of the requested current.
SOC initially equals 20%; subsequent cycles start at the previous final SOC.
The first cycle therefore has a different charge capacity from later cycles.

Use `python main.py --help` for configurable capacity, current, timestep,
rest duration and initial SOC. Output paths must have an existing parent
directory. An existing output file is overwritten. On a thermal limit or
timeout the program exits with a nonzero status and retains partial CSV data.

This is an illustrative digital twin: linear open-circuit voltage, a simple
cycle-aging model and a lumped thermal model. It does not model calendar
aging, cell imbalance, charging efficiency or hardware communication. It must not
be used to control or validate real battery equipment without calibrated
models and independent hardware safety controls.
