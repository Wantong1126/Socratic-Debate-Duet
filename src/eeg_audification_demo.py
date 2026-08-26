"""Record or synthesize EEG and produce a self-contained audification report."""

import argparse
from datetime import datetime
import html
from pathlib import Path
import webbrowser

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.io import wavfile
from scipy.signal import spectrogram

from .eeg_audification import AudificationConfig, CHANNEL_LABELS, process_eeg, signal_metrics
from .window_engine import record_lsl_seconds


def synthetic_recording(seconds, sample_rate=250.0):
    """Repeatable drift-contaminated EEG plus untouched EOG/EMG placeholders."""
    count = int(round(seconds * sample_rate))
    t = np.arange(count) / sample_rate
    eeg = np.column_stack([
        (20 + 4 * ch) * np.sin(2 * np.pi * (3 + 2 * ch) * t + ch * 0.31)
        + (2 + ch) * np.sin(2 * np.pi * (17 + ch) * t)
        + (20_000 + 4_000 * ch) + (120 + 20 * ch) * t / 60.0
        for ch in range(6)
    ])
    return np.column_stack((eeg, np.zeros((count, 2)))), t, sample_rate, "synthetic-drift-distinct-six-channel"


def _plot_channel(path, result, channel):
    raw_t = np.arange(result.raw.shape[0]) / result.input_rate
    fig, axes = plt.subplots(3, 2, figsize=(13, 9), constrained_layout=True)
    axes[0, 0].plot(raw_t, result.raw[:, channel], lw=0.7)
    axes[0, 0].set(title="Raw EEG (offset and drift retained)", xlabel="Time (s)", ylabel="µV")
    axes[0, 1].plot(raw_t, result.cleaned[:, channel], lw=0.7)
    axes[0, 1].set(title="Filtered EEG (0.5–45 Hz, 50 Hz notch)", xlabel="Time (s)", ylabel="µV")
    for row, (audio, title) in enumerate(((result.audified[channel], "Audified"),
                                          (result.modulated[channel], "Modulated")), start=1):
        t = np.arange(len(audio)) / result.config.output_rate
        axes[row, 0].plot(t, audio, lw=0.6)
        axes[row, 0].set(title=f"{title} waveform", xlabel="Time (s)", ylabel="Amplitude")
        nperseg = min(1024, len(audio))
        f, st, power = spectrogram(audio, fs=result.config.output_rate, nperseg=nperseg)
        axes[row, 1].pcolormesh(st, f, 10 * np.log10(power + np.finfo(float).tiny), shading="auto")
        axes[row, 1].set(title=f"{title} spectrogram", xlabel="Time (s)", ylabel="Hz", ylim=(0, 4000))
    fig.suptitle(f"CH{channel + 1} {CHANNEL_LABELS[channel]}")
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _fmt_audio(metrics):
    return f"peak={metrics['peak']:.6f}; RMS={metrics['rms']:.6f}; true audio clipping count={metrics['clipping_count']}"


def _eeg_metrics(raw, cleaned, sample_rate, valid):
    count = len(raw)
    slope = float(np.polyfit(np.arange(count) / sample_rate / 60.0, raw, 1)[0])
    t = np.arange(count) / sample_rate
    basis = np.column_stack((np.sin(2 * np.pi * 50 * t), np.cos(2 * np.pi * 50 * t)))
    coefficients = np.linalg.lstsq(basis, cleaned, rcond=None)[0]
    return {
        "raw_mean": float(np.mean(raw)), "raw_rms": float(np.sqrt(np.mean(raw ** 2))),
        "raw_ptp": float(np.ptp(raw)), "drift_slope": slope,
        "clean_rms": float(np.sqrt(np.mean(cleaned ** 2))),
        "clean_peak": float(np.max(np.abs(cleaned))), "clean_ptp": float(np.ptp(cleaned)),
        "finite_count": int(np.count_nonzero(np.isfinite(raw))), "valid": bool(valid),
        "residual_50_rms": float(np.linalg.norm(coefficients) / np.sqrt(2.0)),
    }


def timestamp_metrics(timestamps, sample_rate):
    intervals = np.diff(np.asarray(timestamps, dtype=float))
    intervals = intervals[np.isfinite(intervals) & (intervals > 0)]
    expected = 1.0 / sample_rate
    if not intervals.size:
        return {"median": None, "p95": None, "maximum": None, "effective_rate": None, "missing_samples": 0}
    gaps = intervals[intervals > 1.5 * expected]
    missing = int(np.sum(np.maximum(0, np.rint(gaps / expected).astype(int) - 1)))
    return {"median": float(np.median(intervals)), "p95": float(np.percentile(intervals, 95)),
            "maximum": float(np.max(intervals)), "effective_rate": float(len(intervals) / np.sum(intervals)),
            "missing_samples": missing}


def write_report(output_dir, result, source_name, timestamps):
    output_dir.mkdir(parents=True, exist_ok=False)
    sections = []
    duration = result.raw.shape[0] / result.input_rate
    for ch, label in enumerate(CHANNEL_LABELS):
        stem = f"ch{ch + 1}_{label}"
        aud_name, mod_name, plot_name = f"{stem}_audified.wav", f"{stem}_modulated.wav", f"{stem}.png"
        wavfile.write(output_dir / aud_name, result.config.output_rate, result.audified[ch])
        wavfile.write(output_dir / mod_name, result.config.output_rate, result.modulated[ch])
        _plot_channel(output_dir / plot_name, result, ch)
        eeg_m = _eeg_metrics(result.raw[:, ch], result.cleaned[:, ch], result.input_rate, result.valid_channels[ch])
        aud_m, mod_m = signal_metrics(result.audified[ch]), signal_metrics(result.modulated[ch])
        status = "valid" if eeg_m["valid"] else "INVALID / FLATLINE (silent WAVs)"
        sections.append(f"""
<section><h2>CH{ch + 1} {label}</h2><img src="{plot_name}" alt="Raw, filtered and audio plots for CH{ch + 1} {label}">
<p><strong>Status: {status}</strong><br>Finite samples: {eeg_m['finite_count']}/{len(result.raw)}<br>
Raw mean/DC offset: {eeg_m['raw_mean']:.6f} µV; RMS: {eeg_m['raw_rms']:.6f} µVrms; peak-to-peak: {eeg_m['raw_ptp']:.6f} µV; estimated linear drift: {eeg_m['drift_slope']:.6f} µV/min<br>
Cleaned RMS: {eeg_m['clean_rms']:.6f} µVrms; peak: {eeg_m['clean_peak']:.6f} µV; peak-to-peak: {eeg_m['clean_ptp']:.6f} µV; 50 Hz residual: {eeg_m['residual_50_rms']:.6f} µVrms<br>
Channel normalization gain: {result.normalization_gain[ch]:.9g} (robust initial {result.initial_gain[ch]:.9g} × safety {result.safety_gain[ch]:.9g})</p>
<p>Method A: input {result.input_rate:g} Hz interpreted at {result.config.audification_rate:g} Hz (×{result.config.audification_rate/result.input_rate:g}), resampled to {result.config.output_rate} Hz; duration {len(result.audified[ch])/result.config.output_rate:.6f} s; {_fmt_audio(aud_m)}; fade {result.config.fade_ms:g} ms.<br><audio controls src="{aud_name}"></audio> <a href="{aud_name}">{aud_name}</a></p>
<p>Method B: original duration at {result.config.output_rate} Hz; duration {len(result.modulated[ch])/result.config.output_rate:.6f} s; {_fmt_audio(mod_m)}; carrier {result.config.carrier_hz:g} Hz, AM depth {result.config.am_depth:g}, FM depth {result.config.fm_depth_hz:g} Hz.<br><audio controls src="{mod_name}"></audio> <a href="{mod_name}">{mod_name}</a></p></section>""")
    timing = timestamp_metrics(timestamps, result.input_rate)
    timing_text = "unavailable" if timing["median"] is None else (
        f"median {timing['median'] * 1000:.6f} ms; p95 {timing['p95'] * 1000:.6f} ms; maximum {timing['maximum'] * 1000:.6f} ms; "
        f"effective rate {timing['effective_rate']:.6f} Hz; estimated missing samples {timing['missing_samples']} (only gaps &gt;1.5× expected 4 ms)")
    c = result.config
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>EEG audification report</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:auto;padding:2rem}}img{{width:100%}}section{{border-top:1px solid #bbb}}code{{background:#eee;padding:.15rem}}</style></head><body>
<h1>EEG audification validation report</h1><p>Source: {html.escape(source_name)}. Recording: {duration:.6f} s, {result.raw.shape[0]} samples × 6 EEG channels at {result.input_rate:g} Hz. Timing: {timing_text}.</p>
<p>Input is the raw OpenBCI LSL <code>TimeSeriesRaw</code> stream. Each EEG channel is processed independently with zero-phase SOS filtering: high-pass {c.highpass_hz:g} Hz order {c.highpass_order}; low-pass {c.lowpass_hz:g} Hz order {c.lowpass_order}; notch {c.notch_hz:g} Hz second-order IIR, Q {c.notch_q:g}. Robust normalization occurs after filtering: percentile {c.robust_percentile:g}, target {c.robust_target:g}, followed by peak safety to 0.999. Flatline threshold: raw peak-to-peak ≤ {c.flatline_peak_to_peak_uv:g} µV. Hardware rail/clipping count: unavailable (no reliable ADS1299 rail threshold supplied). No EEG channels were averaged; EOG/EMG were not processed or sonified.</p>{''.join(sections)}</body></html>"""
    (output_dir / "report.html").write_text(page, encoding="utf-8")
    return output_dir / "report.html"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--open-report", action="store_true")
    parser.add_argument("--audification-rate", type=float, default=8000.0)
    parser.add_argument("--fade-ms", type=float, default=5.0)
    parser.add_argument("--carrier", type=float, default=220.0)
    parser.add_argument("--am-depth", type=float, default=0.5)
    parser.add_argument("--fm-depth", type=float, default=0.0)
    parser.add_argument("--highpass", type=float, default=0.5)
    parser.add_argument("--lowpass", type=float, default=45.0)
    parser.add_argument("--notch", type=float, default=50.0)
    parser.add_argument("--highpass-order", type=int, default=4)
    parser.add_argument("--lowpass-order", type=int, default=4)
    parser.add_argument("--notch-q", type=float, default=30.0)
    parser.add_argument("--robust-percentile", type=float, default=99.5)
    parser.add_argument("--robust-target", type=float, default=0.9)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.seconds <= 0:
        raise SystemExit("--seconds must be positive")
    if args.synthetic:
        samples, timestamps, sample_rate, source = synthetic_recording(args.seconds)
    else:
        try:
            recording = record_lsl_seconds(args.seconds)
        except RuntimeError as exc:
            raise SystemExit(f"Live LSL recording failed: {exc}") from exc
        samples, timestamps, sample_rate, source = recording.samples, recording.timestamps, recording.sample_rate, recording.stream_name
    config = AudificationConfig(audification_rate=args.audification_rate, fade_ms=args.fade_ms,
                                 carrier_hz=args.carrier, am_depth=args.am_depth, fm_depth_hz=args.fm_depth,
                                 highpass_hz=args.highpass, lowpass_hz=args.lowpass, notch_hz=args.notch,
                                 highpass_order=args.highpass_order, lowpass_order=args.lowpass_order,
                                 notch_q=args.notch_q, robust_percentile=args.robust_percentile,
                                 robust_target=args.robust_target)
    result = process_eeg(samples[:, :6], sample_rate, config)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report = write_report(Path("reports/eeg_audification") / stamp, result, source, timestamps)
    print(f"Report: {report.resolve()}")
    print("Per-channel total gains: " + ", ".join(f"{x:.9g}" for x in result.normalization_gain))
    if args.open_report:
        webbrowser.open(report.resolve().as_uri())


if __name__ == "__main__":
    main()
