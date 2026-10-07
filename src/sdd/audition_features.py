"""Raw replay and live share the existing causal ControlSession feature path."""
import math
import hashlib
from pathlib import Path
import numpy as np
from src.eeg_control_demo import ControlSession
from .replay_source import RawSampleReplay


class EnergyProcessor:
    def __init__(self, config, sample_rate=250):
        self.config, self.sample_rate = config, sample_rate
        self.rows, self.calibration_times = [], []
        self.last_time = None
        self.reset()

    def reset(self):
        a = self.config['analysis']
        self.session = ControlSession(
            self.sample_rate, a['update_rate_hz'], a['baseline_seconds'], None,
            window_seconds=a['window_seconds'], analysis_low_hz=a['highpass_hz'],
            analysis_high_hz=a['lowpass_hz'], smoothing_seconds=a['smoothing_seconds'],
            diagnostics=False, transmit=False, frame_callback=self.on_frame,
            warmup_seconds=30, energy_log_scale=True,
            required_quality_channels=(0,), saturation_abs=a['rail_limit_uv']*a['saturation_fraction'])
        self.last_time = None

    def on_frame(self, frame, at):
        bounds = (self.session.engine.bounds or {}).get('eeg1_energy')
        valid = bool(frame.normalized) and not frame.quality_warnings['F3'] and bounds is not None
        valid = bool(valid and bounds[1]-bounds[0] > np.finfo(float).eps*max(1, *map(abs, bounds))*32)
        if not frame.normalized and not frame.quality_warnings['F3']:
            self.calibration_times.append(float(at))
        self.rows.append(dict(t=float(at), raw_energy_uv2=frame.raw['eeg1_energy'],
            amount=frame.normalized.get('eeg1_energy', 0), valid=valid,
            reason='' if valid else 'warmup_calibration_or_invalid_F3',
            quality=frame.quality_warnings, bounds_uv2=list(bounds) if bounds else None))

    def add(self, samples, times):
        # Gaps reset filters, windows, scaling and smoothing; no gap-spanning
        # valid window and no old normalized control survives a restart.
        for begin in range(0, len(samples), 62):
            end = min(begin+62, len(samples))
            stamp = np.asarray(times[begin:end])
            breaks = np.flatnonzero(np.diff(np.r_[self.last_time if self.last_time is not None else stamp[0], stamp]) > .1)
            offset = 0
            for cut in breaks:
                if cut > offset:
                    self.session.add_chunk(samples[begin+offset:begin+cut], stamp[offset:cut])
                self.reset()
                offset = int(cut)
            self.session.add_chunk(samples[begin+offset:end], stamp[offset:])
            self.last_time = float(stamp[-1])


def recompute(directory):
    source = RawSampleReplay(directory)
    processor = EnergyProcessor(source.metadata['config'], source.sample_rate)
    processor.add(source.samples, source.relative)
    valid = [r for r in processor.rows if r['valid']]
    if not valid:
        raise ValueError('recording has no valid calibrated F3 window; no fixture fallback')
    audit = dict(source.audit)
    audit['records_sha256'] = hashlib.sha256((Path(directory)/'records.jsonl').read_bytes()).hexdigest()
    audit['metadata_sha256'] = hashlib.sha256((Path(directory)/'metadata.json').read_bytes()).hexdigest()
    amounts = np.asarray([r['amount'] for r in valid])
    audit.update(valid_feature_windows=len(valid), first_valid_seconds=valid[0]['t'],
        calibration_interval_seconds=[processor.calibration_times[0], processor.calibration_times[-1]],
        energy_bounds_uv2=valid[0]['bounds_uv2'],
        normalized_percentiles=np.percentile(amounts, [0, 5, 50, 95, 100]).tolist(),
        near_endpoint_fraction=float(np.mean((amounts < .02) | (amounts > .98))),
        filter='causal HP .5 Hz order4 -> LP45 order4 -> notch50 Q30 -> HP4 order4 -> LP40 order4; first 30s settling excluded',
        scaling='log10(power uV^2), personal 5th–95th percentiles, clamp then 0.5s EMA; no online range stretching',
        source='replay of operator-confirmed live scalp recording; resting, no condition labels',
        feature='F3 Welch PSD integral 4–40 Hz, uV^2; no full delta measurement')
    return source, processor.rows, audit
