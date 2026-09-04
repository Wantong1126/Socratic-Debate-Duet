# SDD overnight Codex queue

This queue is designed for one unattended Codex run in `D:\sdd-sonification`.
Each task is isolated in its own file so the worker reads only the current scope.

## Install

Copy the `codex_tasks` folder into the repository root so these paths exist:

```text
D:\sdd-sonification\codex_tasks\overnight\00_rules.md
D:\sdd-sonification\codex_tasks\overnight\01_beta_softening.md
...
```

Open the repository in Codex Desktop and paste the contents of
`DISPATCHER_PROMPT.md` as one prompt.

Keep the Windows computer awake and connected to power. This is an agent work
queue, not a guaranteed scheduler: permission errors, environment failures, or
computer sleep can stop it.

In the morning, inspect the final Codex response and the timestamped progress
report created under `reports/overnight/`. Auditory acceptance remains yours.

