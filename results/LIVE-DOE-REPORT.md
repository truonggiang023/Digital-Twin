# Twelve-channel live DOE performance export

Four demo DOE sheets × three cells map to the existing live simulator's channels
1–12. The page at /live-doe.html reads the same Rack as the 3D cycler and polls
every second. Start/Pause/Speed operate that shared state. Every export identifies
the session, time, DOE revision, batch, cell, test and equipment/channel.

The example was captured after advancing the real simulator about 9,150 simulated
seconds. All 12 channels were running, all 12 had a prediction produced by the
existing 600-second discharge-window NASA RF pipeline, and SOH histories were
available. Unlike the static lifecycle examples, these ML features came from
the actual simulator telemetry, not arbitrary illustrative feature values.
They remain experimental and uncalibrated for project cells.

CSV: 12 rows, four DOE IDs, 60 original design columns per row, live values,
ML feature cycle/time and per-channel alarm context. JSON: complete telemetry,
metric definitions, original BOM, SOH/ML histories and alarms.

45 Python tests passed. Browser verified channel count, telemetry advance and
refresh, available ML, 60-field CSV/JSON export, shared Pause, latched STOP and
mobile layout without JavaScript errors.

Limits: generic lithium 3.0–4.2 V model, not calibrated LFP. DOE sheets are metadata
examples and do not determine the simulation physics. No SIB inference is claimed.
Usable Ah and resistance are model outputs, not complete discharge capacity or
pulse DCIR. Partial stage Ah must not be mistaken for full cycle capacity. CE
is unavailable; final target assessment remains pending. Reset creates a new
session and clears in-memory histories. No physical instrument is connected.
