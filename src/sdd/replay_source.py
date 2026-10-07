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


class RawSampleReplay(ReplaySource):
    """Sample-clock replay, retaining original stamps and writer times separately.

    GUI packet interpolation can backtrack slightly. Preserve sample order and
    raw stamps; only the scheduling clock uses a running maximum (no sorting,
    resampling, fabricated samples, or JSONL-write-time pacing).
    """

    def __init__(self, directory, *, clock=time.monotonic):
        import numpy as np
        super().__init__(directory, mode='raw', clock=clock)
        raw = [r for r in self.rows if r['kind'] == 'raw']
        expected = ('F3', 'F4', 'C3', 'C4', 'P3', 'P4', 'vertical_EOG', 'jaw_EMG')
        for row in raw:
            data = row['data']
            if tuple(data['channels']) != expected or data['units'] != ['uV'] * 8:
                raise ValueError('raw replay requires the confirmed eight roles and uV units')
            if data['mode'] != 'live' or data['participant_id'] != 'A':
                raise ValueError('this audition requires a recorded live participant-A source')
            samples = np.asarray(data['samples'], dtype=float)
            stamps = np.asarray(data['sampled_at'], dtype=float)
            if samples.shape != (len(stamps), 8) or not len(stamps):
                raise ValueError('raw samples must be eight columns with one LSL stamp each')
            if not np.isfinite(stamps).all():
                raise ValueError('raw LSL sample clock contains non-finite timestamps')
        rates = {float(r['data']['sample_rate']) for r in raw}
        if len(rates) != 1 or not 80 < next(iter(rates)) <= 2000:
            raise ValueError('inconsistent or unsupported raw sampling rate')
        self.sample_rate = rates.pop()
        self.samples = np.concatenate([r['data']['samples'] for r in raw])
        self.original_lsl = np.concatenate([r['data']['sampled_at'] for r in raw])
        self.written_at = np.concatenate([np.full(len(r['data']['samples']), r['t']) for r in raw])
        self.relative = np.maximum.accumulate(self.original_lsl - self.original_lsl[0])
        dt = np.diff(self.original_lsl)
        if self.relative[-1] <= 0 or np.any(dt < -.1):
            raise ValueError('raw sample clock is stalled or backtracks more than 100ms')
        rail = self.metadata['config']['analysis']['rail_limit_uv'] * self.metadata['config']['analysis']['saturation_fraction']
        self.audit = dict(samples=len(self.samples), channels=list(expected), unit='uV',
            nominal_rate_hz=self.sample_rate, sample_span_seconds=float(self.relative[-1]),
            observed_rate_hz=float((len(self.samples)-1)/self.relative[-1]),
            backwards_timestamp_steps=int(np.sum(dt < 0)),
            minimum_step_seconds=float(dt.min()), maximum_step_seconds=float(dt.max()),
            gaps_over_100ms=int(np.sum(dt > .1)),
            nonfinite_by_channel=np.sum(~np.isfinite(self.samples), axis=0).tolist(),
            saturated_fraction_by_channel=np.mean(abs(self.samples) >= rail, axis=0).tolist(),
            flat_by_channel=(np.ptp(self.samples, axis=0) <= 1e-9).tolist(),
            timing_policy='raw LSL preserved; causal running maximum for playback; writer time unused')
        if abs(self.audit['observed_rate_hz']/self.sample_rate-1) > .2:
            raise ValueError('raw recording arrival rate differs by more than 20 percent')
        self.index = 0

    def restart(self):
        self.index = 0
        self.started = self.clock()
        self.paused_at = None

    def poll_samples(self):
        import numpy as np
        if self.paused_at is not None:
            return self.samples[:0], self.original_lsl[:0], self.relative[:0]
        end = int(np.searchsorted(self.relative, self.clock()-self.started, side='right'))
        begin, self.index = self.index, end
        return self.samples[begin:end], self.original_lsl[begin:end], self.relative[begin:end]

    @property
    def done(self):
        return self.index >= len(self.samples)
