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
    """Repeatable six-channel EEG plus untouched placeholder EOG/EMG columns."""
    count = int(round(seconds * sample_rate))
    t = np.arange(count) / sample_rate
    eeg = np.column_stack([
        (20 + 4 * ch) * np.sin(2 * np.pi * (3 + 2 * ch) * t + ch * 0.31)
        + (2 + ch) * np.sin(2 * np.pi * (17 + ch) * t)
        for ch in range(6)
    ])
    body = np.zeros((count, 2), dtype=float)
    return np.column_stack((eeg, body)), t, sample_rate, "synthetic-distinct-six-channel"


def _plot_channel(path, result, channel):
    raw_t = np.arange(result.raw.shape[0]) / result.input_rate
    fig, axes = plt.subplots(3, 2, figsize=(13, 9), constrained_layout=True)
    axes[0, 0].plot(raw_t, result.raw[:, channel], lw=0.7)
    axes[0, 0].set(title="Raw EEG", xlabel="Time (s)", ylabel="Input units")
    axes[0, 1].plot(raw_t, result.cleaned[:, channel], lw=0.7)
    axes[0, 1].set(title="Cleaned EEG (mean-centred)", xlabel="Time (s)", ylabel="Input units")
    outputs = ((result.audified[channel], "Audified"), (result.modulated[channel], "Modulated"))
    for row, (audio, title) in enumerate(outputs, start=1):
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


def _fmt_metrics(metrics):
    return f"peak={metrics['peak']:.6f}; RMS={metrics['rms']:.6f}; clipping count={metrics['clipping_count']}"


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
        raw_m, clean_m = signal_metrics(result.raw[:, ch]), signal_metrics(result.cleaned[:, ch])
        aud_m, mod_m = signal_metrics(result.audified[ch]), signal_metrics(result.modulated[ch])
        sections.append(f"""
<section><h2>CH{ch + 1} {label}</h2><img src="{plot_name}" alt="Waveforms and spectrograms for CH{ch + 1} {label}">
<p>Raw: {_fmt_metrics(raw_m)}<br>Cleaned: {_fmt_metrics(clean_m)}<br>
Common normalization gain: {result.normalization_gain:.9g} (robust initial {result.initial_gain:.9g} × safety {result.safety_gain:.9g})</p>
<p>Method A: input {result.input_rate:g} Hz interpreted at {result.config.audification_rate:g} Hz, output {result.config.output_rate} Hz; duration {len(result.audified[ch])/result.config.output_rate:.6f} s; {_fmt_metrics(aud_m)}; fade {result.config.fade_ms:g} ms.<br>
<audio controls src="{aud_name}"></audio> <a href="{aud_name}">{aud_name}</a></p>
<p>Method B: input {result.input_rate:g} Hz, output {result.config.output_rate} Hz; duration {len(result.modulated[ch])/result.config.output_rate:.6f} s; {_fmt_metrics(mod_m)}; carrier {result.config.carrier_hz:g} Hz, AM depth {result.config.am_depth:g}, FM depth {result.config.fm_depth_hz:g} Hz.<br>
<audio controls src="{mod_name}"></audio> <a href="{mod_name}">{mod_name}</a></p></section>""")
    gaps = np.diff(timestamps) if len(timestamps) > 1 else np.array([])
    discontinuities = int(np.count_nonzero(np.abs(gaps - 1 / result.input_rate) > 0.5 / result.input_rate))
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>EEG audification report</title>
<style>body{{font:16px system-ui;max-width:1200px;margin:auto;padding:2rem}}img{{width:100%}}section{{border-top:1px solid #bbb}}code{{background:#eee;padding:.15rem}}</style></head><body>
<h1>EEG audification report</h1><p>Source: {html.escape(source_name)}. Recording: {duration:.6f} s, {result.raw.shape[0]} samples × 6 EEG channels at {result.input_rate:g} Hz. Timestamp discontinuities: {discontinuities}.</p>
<p>Cleaning is independent mean-centering only. No EEG channels were averaged; EOG/EMG were not processed or sonified.</p>{''.join(sections)}</body></html>"""
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
                                 carrier_hz=args.carrier, am_depth=args.am_depth, fm_depth_hz=args.fm_depth)
    result = process_eeg(samples[:, :6], sample_rate, config)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report = write_report(Path("reports/eeg_audification") / stamp, result, source, timestamps)
    print(f"Report: {report.resolve()}")
    print(f"Common gain: initial={result.initial_gain:.9g}, safety={result.safety_gain:.9g}, total={result.normalization_gain:.9g}")
    if args.open_report:
        webbrowser.open(report.resolve().as_uri())


if __name__ == "__main__":
    main()
