"""Raw replay and live share the existing causal ControlSession feature path."""
import math
import hashlib
from pathlib import Path
import numpy as np
from scipy.signal import welch
from src.eeg_control_demo import ControlSession
from .replay_source import RawSampleReplay


class EnergyProcessor:
    """One causal feature path for F3 energy or posterior P3/P4 alpha."""
    INPUTS = ('f3_energy', 'posterior_alpha')

    def __init__(self, config, sample_rate=250, input_name='f3_energy'):
        if input_name not in self.INPUTS:
            raise ValueError('input must be f3_energy or posterior_alpha')
        self.config, self.sample_rate, self.input_name = config, sample_rate, input_name
        self.rows, self.calibration_times = [], []
        self.last_time = None
        self.reset()

    def reset(self):
        a = self.config['analysis']
        required = (0,) if self.input_name == 'f3_energy' else (4, 5)
        self.session = ControlSession(
            self.sample_rate, a['update_rate_hz'], a['baseline_seconds'], None,
            window_seconds=a['window_seconds'], analysis_low_hz=a['highpass_hz'],
            analysis_high_hz=a['lowpass_hz'], smoothing_seconds=a['smoothing_seconds'],
            diagnostics=False, transmit=False, frame_callback=self.on_frame,
            warmup_seconds=a.get('warmup_seconds', 30), energy_log_scale=True,
            required_quality_channels=required, saturation_abs=a['rail_limit_uv']*a['saturation_fraction'])
        self.last_time = None
        self.alpha_calibration = []
        self.alpha_bounds = None
        self.alpha_smoothed = None
        self.alpha_frames_seen = 0
        self.alpha_required_frames = max(2, int(round(a['baseline_seconds'] * a['update_rate_hz'])))
        self.alpha_smoothing = (1.0 if a['smoothing_seconds'] <= 0 else
            1.0 - math.exp(-1.0 / (a['update_rate_hz'] * a['smoothing_seconds'])))

    def _posterior_alpha(self, frame, at):
        a = self.config['analysis']
        window = np.asarray(self.session.feature_buffer, dtype=float)
        def power(index):
            segment = min(len(window), int(round(self.sample_rate)))
            freqs, psd = welch(window[:, index], fs=self.sample_rate, nperseg=segment,
                               noverlap=segment // 2)
            mask = (freqs >= a.get('posterior_alpha_low_hz', 8.0)) & (freqs <= a.get('posterior_alpha_high_hz', 13.0))
            return float(np.trapezoid(psd[mask], freqs[mask])) if np.count_nonzero(mask) > 1 else float('nan')
        p3, p4 = power(4), power(5)
        q_p3, q_p4 = frame.quality_warnings['P3'], frame.quality_warnings['P4']
        quality_ok = not q_p3 and not q_p4 and np.isfinite(p3) and np.isfinite(p4)
        raw = (p3 + p4) / 2 if quality_ok else float('nan')
        if quality_ok and self.alpha_bounds is None:
            self.alpha_calibration.append(raw)
            self.alpha_frames_seen += 1
            self.calibration_times.append(float(at))
            if self.alpha_frames_seen >= self.alpha_required_frames:
                values = np.asarray(self.alpha_calibration, dtype=float)
                low, high = np.percentile(values, [a.get('alpha_calibration_low_percentile', 5.0), a.get('alpha_calibration_high_percentile', 95.0)])
                self.alpha_bounds = (float(low), float(high))
        bounds = self.alpha_bounds
        scale_ok = bounds is not None and (bounds[1] - bounds[0] > np.finfo(float).eps * max(1.0, abs(bounds[0]), abs(bounds[1])) * 32)
        if quality_ok and scale_ok:
            amount = float(np.clip((raw - bounds[0]) / (bounds[1] - bounds[0]), 0.0, 1.0))
            previous = amount if self.alpha_smoothed is None else self.alpha_smoothed
            self.alpha_smoothed = previous + self.alpha_smoothing * (amount - previous)
            amount, valid, reason = float(np.clip(self.alpha_smoothed, 0.0, 1.0)), True, ''
        else:
            amount, valid = None, False
            reason = ('P3_or_P4_quality:' + '|'.join(q_p3 + q_p4) if not quality_ok else 'warmup_calibration_or_degenerate_posterior_alpha_range')
        self.rows.append(dict(t=float(at), input='posterior_alpha', raw_posterior_alpha_uv2=raw,
            alpha_p3_uv2=p3, alpha_p4_uv2=p4, amount=amount, valid=valid, reason=reason,
            quality=dict(P3=q_p3, P4=q_p4), bounds_uv2=list(bounds) if bounds else None,
            unit='uV^2', window_seconds=a['window_seconds'], processing_support_seconds=a['window_seconds'],
            smoothing_seconds=a['smoothing_seconds']))

    def on_frame(self, frame, at):
        if self.input_name == 'posterior_alpha':
            self._posterior_alpha(frame, at)
            return
        bounds = (self.session.engine.bounds or {}).get('eeg1_energy')
        valid = bool(frame.normalized) and not frame.quality_warnings['F3'] and bounds is not None
        valid = bool(valid and bounds[1]-bounds[0] > np.finfo(float).eps*max(1, *map(abs, bounds))*32)
        if not frame.normalized and not frame.quality_warnings['F3']:
            self.calibration_times.append(float(at))
        self.rows.append(dict(t=float(at), input='f3_energy', raw_energy_uv2=frame.raw['eeg1_energy'],
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


def recompute(directory, input_name='f3_energy'):
    source = RawSampleReplay(directory)
    processor = EnergyProcessor(source.metadata['config'], source.sample_rate, input_name)
    processor.add(source.samples, source.relative)
    valid = [r for r in processor.rows if r['valid']]
    if not valid:
        raise ValueError(f'recording has no valid calibrated {input_name} window; no fixture fallback')
    audit = dict(source.audit)
    audit['records_sha256'] = hashlib.sha256((Path(directory)/'records.jsonl').read_bytes()).hexdigest()
    audit['metadata_sha256'] = hashlib.sha256((Path(directory)/'metadata.json').read_bytes()).hexdigest()
    amounts = np.asarray([r['amount'] for r in valid])
    audit.update(input=input_name, valid_feature_windows=len(valid), first_valid_seconds=valid[0]['t'],
        calibration_interval_seconds=[processor.calibration_times[0], processor.calibration_times[-1]],
        feature_bounds_uv2=valid[0]['bounds_uv2'],
        normalized_percentiles=np.percentile(amounts, [0, 5, 50, 95, 100]).tolist(),
        near_endpoint_fraction=float(np.mean((amounts < .02) | (amounts > .98))),
        filter='causal HP .5 Hz order4 -> LP45 order4 -> notch50 Q30 -> HP4 order4 -> LP40 order4; first 30s settling excluded',
        scaling='log10(power uV^2), personal 5th–95th percentiles, clamp then 0.5s EMA; no online range stretching',
        source='replay of operator-confirmed live scalp recording; resting, no condition labels',
        feature='F3 Welch PSD integral 4–40 Hz, uV^2; no full delta measurement')
    if input_name == 'posterior_alpha':
        audit['feature'] = 'posterior_alpha: mean(P3, P4) Welch PSD integrals 8-13 Hz, uV^2; absolute power'
        audit['scaling'] = 'own posterior-alpha 5th-95th percentile range, clamp then 0.5s EMA; no online range stretching'
    return source, processor.rows, audit
