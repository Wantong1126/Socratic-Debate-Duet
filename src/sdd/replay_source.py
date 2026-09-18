"""T05: explicit raw/control replay; pause shifts the clock, never catches up."""
import json
from pathlib import Path
import time


class ReplaySource:
    def __init__(self, directory, *, mode, clock=time.monotonic):
        if mode not in ('raw', 'control'):
            raise ValueError('choose raw or control replay explicitly')
        directory = Path(directory)
        self.metadata = json.loads((directory/'metadata.json').read_text(encoding='utf-8'))
        rows = [json.loads(line) for line in
                (directory/'records.jsonl').read_text(encoding='utf-8').splitlines()]
        selected = 'raw' if mode == 'raw' else 'frame'
        if not any(row['kind'] == selected for row in rows):
            raise ValueError(f'recording has no {mode} input')
        self.rows = tuple(row for row in rows if row['kind'] in (selected, 'event'))
        self.mode, self.clock = mode, clock
        self.started = clock()
        self.index = 0
        self.paused_at = None

    def pause(self):
        if self.paused_at is None:
            self.paused_at = self.clock()

    def resume(self):
        if self.paused_at is not None:
            self.started += self.clock() - self.paused_at
            self.paused_at = None

    def poll(self):
        if self.paused_at is not None:
            return []
        elapsed = self.clock() - self.started
        due = []
        while self.index < len(self.rows) and self.rows[self.index]['t'] <= elapsed:
            due.append(self.rows[self.index])
            self.index += 1
        # Preserve source events/raw samples. Only control output is latest-only.
        if self.mode == 'control':
            frames = [row for row in due if row['kind'] == 'frame']
            due = [row for row in due if row['kind'] != 'frame']
            if frames:
                due.append(frames[-1])
            due.sort(key=lambda row: row['t'])
        return due

    @property
    def done(self):
        return self.index >= len(self.rows)
