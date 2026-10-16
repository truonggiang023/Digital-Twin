# Unified project workflow validation

This replaces the previous separation between lifecycle demo snapshots and the
live cycler in the main UI. Start by selecting a project at `/`. Then DOE,
design categories, batch/cell/test registry, Performance and Issues all refer
to the same named cells and channels. Performance includes the original 3D
cycler and live SOH/ML within the project workflow.

Current demo: DOE-P-LFP01 has six prismatic replicates C01–C06 on CH01–06;
DOE-C-LFP01 has six cylindrical replicates C01–C06 on CH07–12. One original
BOM/revision and batch per DOE; unique cell/test/channel and live history per
replicate. The home summary aggregates count, running and SOH mean/min/max.
Editing a shared recipe is blocked after any replicate has begun testing.
Old one-DOE-per-cell records remain preserved, but no longer drive this demo.

Browser verification:
- Workflow hidden until project choice; one DOE and six actual channels per LFP project.
- DOE selection selects the same channel inside embedded 3D.
- 3D selection synchronizes the outer DOE selector.
- Six visible 3D bodies and six channel options/rows, all from the chosen project.
- Switching projects does not reuse the other project's channels.
- No iframe, channels or CSV rows are invented for SIB.
- Project CSV has six rows, cell names include the DOE and replicate suffix, and all 60 original fields.
- Fault on CH08 appears as an issue against DOE-C-LFP01 / C02 in CYLINDRICAL LFP01.
- Design editor has 60 fields and saves the same live DOE as revision V2.
- Mobile width checked; no JavaScript errors.

51 Python tests passed, including source identity, no old static-demo leakage,
project filtering, persisted DOE definitions, fault/issue resolution preserving
STOP, revision protection, and the existing live ML, aging, DOE and safety suites.

Example PNG/CSV/JSON files were captured from the same running simulated rack
at approximately 9,000 simulated seconds. No hardware is connected. Recipes
are design metadata, not calibrated simulation parameters. Usable Ah and model
resistance are not completed discharge capacity or pulse DCIR; CE/complete target
assessment remain pending. ML remains experimental and uncalibrated for LFP/SIB.
Whole-rack Start/Pause/Reset applies even in a project-filtered view. Runtime
telemetry is memory-only; original DOE information and issues persist locally.
