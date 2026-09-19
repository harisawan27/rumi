# Artifact contract parity fixtures

These are synthetic data for Python tests and future TypeScript parity tests.
They are not generated executable content or a record of actual study activity.

- `valid_study_tracker.json`: server-assembled `GeneratedArtifact`; starts empty.
- `valid_color_edit.json`, `valid_graph_edit.json`: `OutputDecision` edit variants.
- `invalid_renderer.json`, `invalid_color.json`: `OutputDecision` inputs that must fail.

Use the same JSON unchanged in future client tests. Dates serialize as
`YYYY-MM-DD`, timestamps include timezone offsets, and tuples serialize as JSON
arrays. Server-supplied IDs/provenance belong in the artifact envelope; model
create decisions cannot provide them. Parsing a valid ID is not authorization.
