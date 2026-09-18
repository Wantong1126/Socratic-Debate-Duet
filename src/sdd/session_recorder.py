"""T03: append-only JSONL with explicit live-recording consent."""
from dataclasses import asdict
import json
from pathlib import Path


class SessionRecorder:
    def __init__(self, directory, *, session_id, config, code_version, source,
                 seed, monotonic_origin, wall_origin, allow_live_recording=False):
        if (source.get('mode') == 'live' or source.get('real_eeg')) and not allow_live_recording:
            raise PermissionError('live acquisition recording must be explicitly enabled')
        self.allow_live = allow_live_recording
        self.session_id = session_id
        self.origin = monotonic_origin
        self.last_at = float('-inf')
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        metadata = dict(schema_version=1, session_id=session_id, config=config,
                        code_version=code_version, source=source, seed=seed,
                        monotonic_origin=monotonic_origin, wall_origin=wall_origin,
                        clock='seconds on shared monotonic timeline',
                        simulated=source.get('mode') == 'fixture')
        (directory / 'metadata.json').write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        self.stream = (directory / 'records.jsonl').open('x', encoding='utf-8')

    def write(self, kind, at, data, *, live=False):
        if live and not self.allow_live:
            raise PermissionError('live recording disabled')
        if at < self.last_at or at < self.origin:
            raise ValueError('records must use one ordered monotonic timeline')
        row = dict(kind=kind, t=at-self.origin, data=data)
        serialized = json.dumps(row, ensure_ascii=False, allow_nan=False)
        self.stream.write(serialized + '\n')
        self.stream.flush()
        self.last_at = at

    def frame(self, frame):
        if frame.session_id != self.session_id:
            raise ValueError('session mismatch')
        self.write('frame', frame.received_at, frame.to_dict(), live=frame.mode == 'live')

    def event(self, event):
        if event.session_id != self.session_id:
            raise ValueError('session mismatch')
        self.write('event', event.at, asdict(event))

    def raw(self, *, at, sampled_at, samples, sample_rate, channels, units,
            mode, participant_id='A'):
        if mode not in ('live', 'fixture') or participant_id not in ('A', 'B'):
            raise ValueError('raw source mode/identity required')
        self.write('raw', at, dict(sampled_at=sampled_at, samples=samples,
                   sample_rate=sample_rate, channels=channels, units=units,
                   mode=mode, participant_id=participant_id), live=mode == 'live')

    def close(self):
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
