# Unified project workflow validation

This replaces the previous separation between lifecycle demo snapshots and the
live cycler in the main UI. Start by selecting a project at `/`. Then DOE,
design categories, batch/cell/test registry, Performance and Issues all refer
to the same named cells and channels. Performance includes the original 3D
cycler and live SOH/ML within the project workflow.

Each cell is named for its DOE. DOE-01–06 / CH01–06 are PRISMATIC LFP01;
DOE-07–12 / CH07–12 are CYLINDRICAL LFP01. Thus the new demo has 12 DOE/cell
identities, replacing the earlier four-DOE grouping. SIB is explicitly empty.
The shared original DOE definitions persist in SQLite and can be edited before
testing, creating revisions. Running-channel metadata cannot be rewritten.

Browser verification:
- Workflow hidden until project choice; six actual channels per LFP project.
- DOE selection selects the same channel inside embedded 3D.
- 3D selection synchronizes the outer DOE selector.
- Six visible 3D bodies and six channel options/rows, all from the chosen project.
- Switching projects does not reuse the other project's channels.
- No iframe, channels or CSV rows are invented for SIB.
- Project CSV has six rows, DOE name equals cell name, and all 60 original fields.
- Fault on CH08 appears as an issue against DOE-08 in CYLINDRICAL LFP01.
- Design editor has 60 fields and saves the same live DOE as revision V2.
- Mobile width checked; no JavaScript errors.

50 Python tests passed, including source identity, no old static-demo leakage,
project filtering, persisted DOE definitions, fault/issue resolution preserving
STOP, revision protection, and the existing live ML, aging, DOE and safety suites.

Example PNG/CSV/JSON files were captured from the same running simulated rack
at approximately 9,000 simulated seconds. No hardware is connected. Recipes
are design metadata, not calibrated simulation parameters. Usable Ah and model
resistance are not completed discharge capacity or pulse DCIR; CE/complete target
assessment remain pending. ML remains experimental and uncalibrated for LFP/SIB.
Whole-rack Start/Pause/Reset applies even in a project-filtered view. Runtime
telemetry is memory-only; original DOE information and issues persist locally.
