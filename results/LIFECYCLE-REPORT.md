# Lifecycle registry demo validation

The Navigation Home now links Project Master → DOE Register/Revision → Design
Input → Batch/Cell Registry → Test/Equipment/Channel → Performance and Issues.

Synthetic examples: four projects, eight immutable DOE V01 records, eight
batches, 24 cells/tests, eight running scenario snapshots, eight completed and
eight stopped (51°C), eight critical issues with owner/due date. Demo insertion
is explicit and idempotent, never deletes local records. Revise a design using
the same DOE code with a new revision number; existing batches keep their original
revision and complete original 60-field BOM.

CSV example contains six tests from PRISMATIC LFP01, every original BOM field,
full trace identifiers and source labels, performance and issue context. JSON
contains cycle histories and model input/output provenance. These are synthetic
cycle summaries, not raw instrument measurements.

42 Python tests pass, covering registry referential integrity, source isolation,
immutable revisions, cycle-order rejection with rollback, channel conflicts,
persistence, temperature STOP and issue resolution without clearing STOP, plus
existing DOE/live ML/aging/integration suites. Chromium verified demo creation,
four-project filtering, CSV with 60 original fields, SOH curve/experimental ML,
issue rows, mobile width and legacy cycler loading without JavaScript errors.

Limits: registry cycle imports do not command hardware. Test running labels in
the demo are snapshots. Temperature >=45°C import sets registry STOP only.
NASA RF predictions here use synthetic illustrative features, are uncalibrated
for LFP, and can disagree strongly with capacity-derived SOH; no SIB or manual
prediction is invented. Pass evaluates capacity minimum and temperature only,
not every BOM target. DCIR is supplied, CE calculated from cycle Ah. The original
12-channel live simulator/ML remains separate and accessible at /index.html.
