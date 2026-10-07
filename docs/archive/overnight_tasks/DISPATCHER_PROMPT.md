Work inside `D:\sdd-sonification` and run the overnight task queue found in
`codex_tasks/overnight/`.

1. Read `00_rules.md` completely.
2. List the numbered task filenames, but do not read all task bodies at once.
3. Execute `01` through `07` strictly in numeric order. Before each task, read
   only that task file plus `00_rules.md`.
4. If fresh subagents are available, use one fresh worker per task sequentially,
   passing only the rules and current task. Never edit in parallel. Otherwise
   execute sequentially in this session.
5. After every task, inspect its diff, run its focused tests, append a concise
   checkpoint to the overnight progress report, and then continue automatically.
   Do not wait for me between successful tasks.
6. An auditory check marked `PENDING HUMAN LISTENING` is not a blocker. A failed
   test, unsafe conflict, permission requirement, missing required dependency,
   or ambiguous destructive action is a blocker: record it and stop instead of
   guessing or continuing dependent work.
7. After task `07`, give one final report. Do not commit.

